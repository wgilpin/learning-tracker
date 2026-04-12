"""Chapter Scribe: drafts chapters and responds to margin comments using Gemini."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.config import settings
from documentlm_core.schemas import TokenUsage
from documentlm_core.services.chroma import get_chroma_client, query_topic_chunks_with_sources

logger = logging.getLogger(__name__)

_APP_NAME = "chapter_scribe"

_CHAPTER_INSTRUCTION = """You are an academic tutor writing clear, well-structured study chapters.

The chapter TITLE and DESCRIPTION define exactly what this chapter must cover — they are
authoritative. Write the chapter about that specific topic regardless of what the provided
sources contain.

The chapter should:
- Open with a clear explanation of what this topic is and why it matters
- Cover the key concepts, definitions, and ideas with concrete examples
- Use plain, precise language — accessible but rigorous
- Be structured with markdown headings (##) for major sections
- End with a concise summary of what was covered

If "Prior chapters" are listed in the prompt, you may briefly connect this topic to them.
If no prior chapters are listed, this is the first chapter — do NOT reference or imply any
previous material.

Write only the chapter content — no preamble, no "here is your chapter" introductions.

You will be given a numbered "Available sources" list. Use these sources to support claims
where they are relevant to the chapter topic. When making a factual claim supported by a
source, insert an inline citation marker immediately after the relevant sentence, in the
style [1].

Rules:
- Write comprehensively about the stated chapter topic — the title and description are the
  subject, not the sources.
- Only cite sources from the "Available sources" list provided.
- You may cite the same source multiple times.
- Only cite a source for a claim it actually supports — do not force citations onto
  off-topic material.
- If sources do not cover an aspect of the topic, write from your knowledge without
  inventing a citation.
- At the very end, after your summary, add a "## References" section listing ONLY the
  sources you actually cited, preserving their original numbers. Format each line exactly as:
  [n] Full citation text as provided in the reference list.
- Do not invent sources or cite sources not in the list.
"""

_RELEVANCE_CHECK_INSTRUCTION = (
    "You are deciding whether retrieved source excerpts are relevant and sufficient to write "
    "a chapter on a given topic. "
    "Respond with ONLY the single word YES or NO — no explanation, no punctuation."
)

_COMMENT_INSTRUCTION = """You are an academic tutor responding to a student's question
or comment on a passage they are reading.

The student has highlighted a paragraph and asked a question or left a note.
Provide a clear, helpful response that:
- Directly addresses what the student asked or noted
- Explains or expands on the concept if they seem confused
- Keeps the response concise (2-4 sentences) unless the question warrants more depth

Respond only with the answer — no preamble.
"""


@dataclass
class ChapterDraft:
    content: str
    cited_source_ids: list[uuid.UUID] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)


def _format_source_for_prompt(n: int, source) -> str:  # source: Source ORM object
    parts: list[str] = []
    if source.authors:
        parts.append(", ".join(source.authors))
    parts.append(f"({source.publication_date.year})" if source.publication_date else "(n.d.)")
    parts.append(source.title)
    if source.doi:
        parts.append(f"DOI:{source.doi}")
    elif source.url:
        parts.append(source.url)
    return f"[{n}] " + " ".join(parts)


def _extract_cited_indices(content: str) -> set[int]:
    return {int(m) for m in re.findall(r"\[(\d+)\]", content)}


async def _chunks_cover_topic(
    query_text: str,
    chunk_pairs: list[tuple[str, uuid.UUID]],
) -> bool:
    """Ask the LLM whether the retrieved chunks actually cover the chapter topic.

    Returns True if the LLM judges the excerpts sufficient, False otherwise.
    On any error, returns False so the Academic Scout fallback is triggered.
    """
    excerpts = "\n\n".join(
        f"[{i + 1}] {chunk[:400]}" for i, (chunk, _) in enumerate(chunk_pairs[:6])
    )
    prompt = (
        f"Chapter topic: {query_text}\n\n"
        f"Retrieved source excerpts:\n{excerpts}\n\n"
        f"Are these excerpts relevant and sufficient to write a comprehensive chapter on the "
        f"topic above — not just tangentially related, but actually covering it? YES or NO."
    )
    try:
        response, _usage = await _run_agent(_RELEVANCE_CHECK_INSTRUCTION, prompt)
        result = response.strip().upper().startswith("YES")
        logger.info(
            "Chapter Scribe relevance check for %r: %s", query_text[:60], "YES" if result else "NO"
        )
        return result
    except Exception:
        logger.exception("Chapter Scribe: relevance check failed — treating as insufficient")
        return False


async def _run_agent(instruction: str, prompt: str) -> tuple[str, TokenUsage]:
    agent = Agent(
        name="chapter_scribe",
        model=settings.gemini_model,
        instruction=instruction,
    )
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id="system")
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    logger.debug(
        "Chapter Scribe LLM call — instruction:\n%s\n\n--- prompt ---\n%s",
        instruction,
        prompt,
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    reply_text: str | None = None
    usage = TokenUsage()
    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            reply_text = event.content.parts[0].text
            if event.usage_metadata:
                usage = TokenUsage(
                    input_tokens=event.usage_metadata.prompt_token_count or 0,
                    output_tokens=event.usage_metadata.candidates_token_count or 0,
                )
            break

    if not reply_text:
        raise RuntimeError("Chapter Scribe returned no response")

    return reply_text, usage


async def _scout_and_requery(
    topic_id: uuid.UUID,
    item_title: str,
    query_text: str,
    session: AsyncSession,
    chroma_client,
) -> list[tuple[str, uuid.UUID]]:
    """Run Academic Scout to find new sources for a chapter query.

    ``item_title`` is used as the web search query (concise, searchable).
    ``query_text`` (title + description) is used for the ChromaDB re-query.

    Creates UserSourceRef entries so the new sources are visible to this topic,
    then re-queries ChromaDB. Returns the updated chunk pairs (may be empty if
    the scout finds nothing or API keys are not configured).
    """
    from documentlm_core.agents.academic_scout import run_academic_scout
    from documentlm_core.db.models import Topic, UserSourceRef

    logger.warning(
        "Chapter Scribe: chunks insufficient for %r — triggering Academic Scout", item_title
    )
    try:
        topic_obj = (
            await session.execute(select(Topic).where(Topic.id == topic_id))
        ).scalar_one_or_none()
        if topic_obj is None:
            logger.warning("Chapter Scribe: topic %s not found — skipping scout", topic_id)
            return []

        new_ids = await run_academic_scout(topic_id, item_title, session)
        # run_academic_scout commits per source; now link each new source via UserSourceRef
        for src_id in new_ids:
            existing = (
                await session.execute(
                    select(UserSourceRef).where(
                        UserSourceRef.user_id == topic_obj.user_id,
                        UserSourceRef.source_id == src_id,
                        UserSourceRef.topic_id == topic_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    UserSourceRef(
                        id=uuid.uuid4(),
                        user_id=topic_obj.user_id,
                        source_id=src_id,
                        topic_id=topic_id,
                    )
                )
        await session.flush()

        # Re-query with all topic sources now including newly discovered ones
        refs_result = await session.execute(
            select(UserSourceRef).where(UserSourceRef.topic_id == topic_id)
        )
        updated_source_ids = [ref.source_id for ref in refs_result.scalars().all()]
        chunk_pairs = query_topic_chunks_with_sources(
            chroma_client, updated_source_ids, query_text, n_results=10, max_distance=1.1
        )
        logger.info(
            "Chapter Scribe post-scout retrieved %d chunk(s) from ChromaDB", len(chunk_pairs)
        )
        return chunk_pairs

    except Exception:
        logger.exception(
            "Chapter Scribe: Academic Scout fallback failed — continuing without new sources"
        )
        return []


async def run_chapter_scribe(
    item_id: uuid.UUID,
    item_title: str,
    topic_id: uuid.UUID,
    session: AsyncSession,
    item_description: str | None = None,
    learning_objectives: list[dict] | None = None,
) -> ChapterDraft:
    logger.info("Chapter Scribe starting for item_id=%s title=%r", item_id, item_title)
    from documentlm_core.db.models import Source
    from documentlm_core.services.chapter import get_context_summaries

    # Retrieve relevant source chunks from ChromaDB (with source IDs)
    query_text = f"{item_title} {item_description or ''}".strip()
    logger.info("Chapter Scribe querying ChromaDB for chunks related to %r", item_title)

    from documentlm_core.db.models import UserSourceRef
    refs_result = await session.execute(
        select(UserSourceRef).where(UserSourceRef.topic_id == topic_id)
    )
    topic_source_ids = [ref.source_id for ref in refs_result.scalars().all()]

    chroma_client = get_chroma_client()
    chunk_pairs = query_topic_chunks_with_sources(
        chroma_client, topic_source_ids, query_text, n_results=10
    )
    logger.info("Chapter Scribe retrieved %d candidate chunk(s) from ChromaDB", len(chunk_pairs))

    # Ask the LLM whether the chunks actually cover this chapter topic.
    # If not (or if there are no chunks at all), trigger Academic Scout to find better sources.
    chunks_sufficient = chunk_pairs and await _chunks_cover_topic(query_text, chunk_pairs)
    if not chunks_sufficient:
        chunk_pairs = await _scout_and_requery(
            topic_id, item_title, query_text, session, chroma_client
        )

    # Deduplicate source IDs preserving similarity order
    chunk_source_ids = list(dict.fromkeys(src_id for _, src_id in chunk_pairs))
    logger.info("Chapter Scribe chunk source IDs from ChromaDB: %s", chunk_source_ids)

    sources: list = []
    if chunk_source_ids:
        result = await session.execute(
            select(Source).where(Source.id.in_(chunk_source_ids))
        )
        by_id = {s.id: s for s in result.scalars().all()}
        sources = [by_id[sid] for sid in chunk_source_ids if sid in by_id]
    else:
        logger.info(
            "Chapter Scribe: no ChromaDB chunks for item_id=%s — generating without sources",
            item_id,
        )

    logger.info("Chapter Scribe found %d verified source(s) for citation", len(sources))

    # source_map: citation number (1-based) → source UUID
    source_map: dict[int, uuid.UUID] = {n: s.id for n, s in enumerate(sources, 1)}

    logger.info("Chapter Scribe fetching prior chapter summaries for context")
    context_summaries = await get_context_summaries(session, topic_id, item_id)
    logger.info("Chapter Scribe found %d prior chapter summary(ies)", len(context_summaries))

    topic_line = f"Topic: {item_title}"
    if item_description:
        topic_line += f"\nDescription: {item_description}"
    prompt_parts = [topic_line]

    if learning_objectives:
        obj_lines = "\n".join(
            f"- [{o.get('bloom_level', '')}] {o.get('text', '')}"
            for o in learning_objectives
        )
        prompt_parts.append(
            f"Learning objectives for this chapter (ensure the content enables students to "
            f"achieve each of these):\n{obj_lines}"
        )

    if sources:
        # Group chunks by source
        chunks_by_source: dict[uuid.UUID, list[str]] = {}
        for chunk_text, src_id in chunk_pairs:
            if src_id in {s.id for s in sources}:
                chunks_by_source.setdefault(src_id, []).append(chunk_text)

        source_material_parts = []
        for n, source in enumerate(sources, 1):
            excerpt = "\n".join(chunks_by_source.get(source.id, [])[:3])
            source_material_parts.append(f"[{n}] {source.title}\n{excerpt}")
        prompt_parts.append(
            "Available sources (cite by number in your prose):\n\n"
            + "\n\n---\n\n".join(source_material_parts)
        )

        refs_block = "\n".join(
            _format_source_for_prompt(n, s) for n, s in enumerate(sources, 1)
        )
        prompt_parts.append(f"Reference list for your ## References section:\n{refs_block}")

    if context_summaries:
        summaries_text = "\n".join(f"- {s}" for s in context_summaries)
        prompt_parts.append(f"Prior chapters in this topic (for context):\n{summaries_text}")
    prompt_parts.append("Write the chapter now.")

    logger.info(
        "Chapter Scribe calling LLM to draft chapter %r (model=%s, sources=%d)",
        item_title,
        settings.gemini_model,
        len(sources),
    )
    content, scribe_usage = await _run_agent(_CHAPTER_INSTRUCTION, "\n\n".join(prompt_parts))
    logger.info("Chapter Scribe complete for item_id=%s chars=%d", item_id, len(content))

    cited_indices = _extract_cited_indices(content)
    cited_source_ids = [source_map[n] for n in sorted(cited_indices) if n in source_map]
    logger.info("Chapter Scribe extracted %d citation(s) from content", len(cited_source_ids))

    if sources and not cited_source_ids:
        logger.warning(
            "Chapter Scribe returned no citations for item_id=%s despite having sources. "
            "Content:\n%s",
            item_id,
            content,
        )

    return ChapterDraft(
        content=content, cited_source_ids=cited_source_ids, token_usage=scribe_usage
    )


async def respond_to_comment(
    comment_id: uuid.UUID,
    chapter_id: uuid.UUID,
    session: AsyncSession,
) -> str:
    logger.info(
        "Chapter Scribe responding to comment_id=%s on chapter_id=%s", comment_id, chapter_id
    )
    from sqlalchemy import select

    from documentlm_core.db.models import AtomicChapter, MarginComment

    logger.info("Chapter Scribe fetching comment and chapter content")
    comment_result = await session.execute(
        select(MarginComment).where(MarginComment.id == comment_id)
    )
    comment = comment_result.scalar_one_or_none()
    if comment is None:
        raise ValueError(f"MarginComment {comment_id} not found")

    chapter_result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    if chapter is None:
        raise ValueError(f"AtomicChapter {chapter_id} not found")

    logger.info(
        "Chapter Scribe calling LLM to answer comment on paragraph %r (model=%s)",
        comment.paragraph_anchor,
        settings.gemini_model,
    )
    prompt = (
        f"The student is reading a chapter. They highlighted the following paragraph:\n\n"
        f"[Paragraph anchor: {comment.paragraph_anchor}]\n\n"
        f"Their comment or question:\n{comment.content}\n\n"
        f"Chapter excerpt for context (first 500 chars):\n{chapter.content[:500]}"
    )

    response, _usage = await _run_agent(_COMMENT_INSTRUCTION, prompt)
    logger.info(
        "Chapter Scribe comment response complete for comment_id=%s chars=%d",
        comment_id,
        len(response),
    )
    return response
