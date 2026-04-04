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
from documentlm_core.services.chroma import get_chroma_client, query_topic_chunks_with_sources

logger = logging.getLogger(__name__)

_APP_NAME = "chapter_scribe"

_CHAPTER_INSTRUCTION = """You are an academic tutor writing clear, well-structured study chapters.

Given a topic and sub-topic title, write a comprehensive chapter that a student can learn from.

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

You will be given a numbered "Available sources" list. When making a factual claim
supported by a source, insert an inline citation marker immediately after the relevant
sentence, in the style [1].

Rules:
- Only cite sources from the "Available sources" list provided.
- You may cite the same source multiple times.
- Not every sentence needs a citation — only claims directly supported by a listed source.
- Every sentence or paragraph that can be supported by a ctiation must have a citation marker.
- Material should not come from your training data — only from the provided sources.
- Therefore every paragraph should have a citation marker, since all material must be sourced.
- At the very end, after your summary, add a "## References" section listing ONLY the
  sources you actually cited, preserving their original numbers. Format each line exactly as:
  [n] Full citation text as provided in the reference list.
- Do not invent sources or cite sources not in the list.
"""

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


async def _run_agent(instruction: str, prompt: str) -> str:
    agent = Agent(
        name="chapter_scribe",
        model=settings.gemini_model,
        instruction=instruction,
    )
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=_APP_NAME, user_id="system")
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    reply_text: str | None = None
    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            reply_text = event.content.parts[0].text
            break

    if not reply_text:
        raise RuntimeError("Chapter Scribe returned no response")

    return reply_text


async def run_chapter_scribe(
    item_id: uuid.UUID,
    item_title: str,
    topic_id: uuid.UUID,
    session: AsyncSession,
    item_description: str | None = None,
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
    logger.info("Chapter Scribe retrieved %d source chunk(s) from ChromaDB", len(chunk_pairs))

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

    prompt_parts = [f"Topic: {item_title}"]

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
    content = await _run_agent(_CHAPTER_INSTRUCTION, "\n\n".join(prompt_parts))
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

    return ChapterDraft(content=content, cited_source_ids=cited_source_ids)


async def respond_to_comment(
    comment_id: uuid.UUID,
    chapter_id: uuid.UUID,
    session: AsyncSession,
) -> str:
    logger.info("Chapter Scribe responding to comment_id=%s on chapter_id=%s", comment_id, chapter_id)
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

    response = await _run_agent(_COMMENT_INSTRUCTION, prompt)
    logger.info("Chapter Scribe comment response complete for comment_id=%s chars=%d", comment_id, len(response))
    return response
