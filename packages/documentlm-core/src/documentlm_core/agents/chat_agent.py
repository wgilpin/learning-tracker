"""Chat Agent: intent classification and streaming response agents for the chat panel."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.config import settings
from documentlm_core.schemas import ChatMessage
from documentlm_core.services.chroma import get_chroma_client, query_topic_chunks_with_sources

logger = logging.getLogger(__name__)

_APP_NAME = "chat_agent"

_INTENT_INSTRUCTION = """You are an intent classifier for a learning assistant chat panel.

Classify the user's latest message into exactly one of these intents:
- "quiz": user wants to take a multiple-choice quiz on a chapter
- "socratic": user wants to be asked a question or led through Socratic dialogue
- "expand": user wants a deeper explanation or more detail on a specific concept
- "extend_syllabus": user wants to add new sections or topics to the syllabus
  (e.g. "add a section on X", "extend the syllabus with Y", "include coverage of Z")
- "qa": any other question or conversation about the topic material

Respond with exactly one word: quiz, socratic, expand, extend_syllabus, or qa. Nothing else.
"""

_QA_INSTRUCTION = """You are a knowledgeable academic tutor helping a student understand material.

You are given:
1. The chapter the student is currently studying
2. Supplementary source excerpts from the broader topic
3. The full list of chapter titles in this course

Before responding, ask yourself: is this question clearly the focus of a DIFFERENT chapter in the
chapter list (not the current one)?
- If YES: briefly acknowledge the question and note that it will be covered in an upcoming chapter.
  Give at most one orienting sentence — do not explain the answer.
- If NO: if the answer is short (1-2 sentences), answer directly. Otherwise respond Socratically —
  ask ONE short guiding question to help the student think through the answer themselves.

Rules:
- Never give long explanations in response to a direct question.
- Never open with "Based on the provided source material" or similar phrases.
- If you cite a specific excerpt, use inline notation like "[2]".
- If neither the chapter nor the excerpts cover the question, say so honestly.
"""

_SOCRATIC_INSTRUCTION = """You are a Socratic tutor helping a student develop their understanding.

You are given the chapter the student is currently studying, followed by supplementary source
excerpts from the broader topic.

Rules:
- Ask exactly ONE question at a time — never multiple questions in one response.
- Never directly correct the student or give away the answer.
- Follow the student's answer closely: probe the gap in their understanding, not a script.
- If the student demonstrates clear understanding of the concept, advance to a harder question or
  acknowledge mastery.
- Base your questions primarily on the chapter content provided.
- Keep your response focused: one question, briefly framed.
"""

_EXPAND_INSTRUCTION = """You are an academic tutor providing enriched explanations.

You are given the chapter the student is currently studying, followed by supplementary source
excerpts from the broader topic.

The student wants to explore a concept more deeply.
Extract the key concept from their message and provide a richer, more detailed explanation.
Draw primarily on the chapter content, then expand with the supplementary source excerpts.
If neither covers the concept adequately, say so and offer what you can from general
knowledge, clearly labelling it as such.

Use markdown for structure. Be thorough but not padded.
"""


async def _get_chapter_context(
    session: AsyncSession, chapter_id: uuid.UUID
) -> tuple[str, str] | None:
    """Return (title, content) for a chapter, or None if not found."""
    from documentlm_core.db.models import AtomicChapter, SyllabusItem

    result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        return None
    item_result = await session.execute(
        select(SyllabusItem).where(SyllabusItem.id == chapter.syllabus_item_id)
    )
    item = item_result.scalar_one_or_none()
    title = item.title if item else "Chapter"
    return title, chapter.content


async def _get_topic_chapter_titles(session: AsyncSession, topic_id: uuid.UUID) -> list[str]:
    """Return all syllabus item titles for a topic."""
    from documentlm_core.db.models import SyllabusItem

    result = await session.execute(
        select(SyllabusItem.title)
        .where(SyllabusItem.topic_id == topic_id)
        .order_by(SyllabusItem.created_at)
    )
    return list(result.scalars().all())


async def _get_topic_source_ids(session: AsyncSession, topic_id: uuid.UUID) -> list[uuid.UUID]:
    from documentlm_core.db.models import UserSourceRef

    result = await session.execute(
        select(UserSourceRef).where(UserSourceRef.topic_id == topic_id)
    )
    return [ref.source_id for ref in result.scalars().all()]


async def _run_agent(instruction: str, prompt: str) -> str:
    agent = Agent(
        name="chat_agent",
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
        raise RuntimeError("Chat agent returned no response")

    return reply_text


async def _run_agent_stream(instruction: str, prompt: str) -> AsyncIterator[str]:
    agent = Agent(
        name="chat_agent_stream",
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

    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    yield part.text


def _build_conversation_prompt(messages: list[ChatMessage]) -> str:
    parts = []
    for msg in messages:
        prefix = "Student" if msg.role == "user" else "Assistant"
        parts.append(f"{prefix}: {msg.content}")
    return "\n".join(parts)


def _build_source_context(chunk_pairs: list[tuple[str, uuid.UUID]]) -> str:
    if not chunk_pairs:
        return ""
    numbered = "\n\n---\n\n".join(
        f"[{i + 1}] {text}" for i, (text, _) in enumerate(chunk_pairs[:8])
    )
    return f"Source excerpts (supplementary context from the broader topic):\n\n{numbered}"


def _build_chapter_block(title: str, content: str) -> str:
    return f"Chapter: {title}\n\n{content[:6000]}"


def _build_chapter_list_block(titles: list[str], current_title: str | None = None) -> str:
    if not titles:
        return ""
    lines = []
    for t in titles:
        marker = " ← current chapter" if t == current_title else ""
        lines.append(f"- {t}{marker}")
    return "Course chapters:\n" + "\n".join(lines)


async def classify_intent(
    message: str,
) -> Literal["quiz", "socratic", "expand", "qa", "extend_syllabus"]:
    """Classify the user's intent from their latest message."""
    logger.debug("classify_intent: classifying message=%r", message[:80])
    raw = await _run_agent(_INTENT_INSTRUCTION, f"Message: {message}")
    intent = raw.strip().lower()
    logger.debug("classify_intent: raw=%r intent=%r", raw, intent)
    if intent in ("quiz", "socratic", "expand", "qa", "extend_syllabus"):
        return intent  # type: ignore[return-value]
    logger.warning("classify_intent: unrecognised intent %r, defaulting to qa", raw)
    return "qa"


async def stream_qa_response(
    messages: list[ChatMessage],
    topic_id: uuid.UUID,
    session: AsyncSession,
    chapter_id: uuid.UUID | None = None,
) -> AsyncIterator[str]:
    """Stream a Q&A response using chapter content and ChromaDB context."""
    logger.info("stream_qa_response: topic_id=%s chapter_id=%s messages=%d", topic_id, chapter_id, len(messages))

    source_ids = await _get_topic_source_ids(session, topic_id)
    chroma_client = get_chroma_client()

    latest_question = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )

    if source_ids:
        chunk_pairs = query_topic_chunks_with_sources(
            chroma_client, source_ids, latest_question, n_results=6, max_distance=1.1
        )
        logger.debug("stream_qa_response: retrieved %d chunks from ChromaDB", len(chunk_pairs))
    else:
        chunk_pairs = []
        logger.info("stream_qa_response: no source material for topic_id=%s", topic_id)

    chapter_ctx = None
    if chapter_id is not None:
        chapter_ctx = await _get_chapter_context(session, chapter_id)
        logger.debug("stream_qa_response: chapter_ctx fetched=%s", chapter_ctx is not None)

    if not chunk_pairs and chapter_ctx is None:
        yield (
            "I don't have any source material for this topic yet. "
            "Please add some sources first so I can answer questions based on the material."
        )
        return

    chapter_titles = await _get_topic_chapter_titles(session, topic_id)
    current_title = chapter_ctx[0] if chapter_ctx is not None else None
    chapter_list_block = _build_chapter_list_block(chapter_titles, current_title)

    source_context = _build_source_context(chunk_pairs)
    conversation = _build_conversation_prompt(messages)

    if chapter_ctx is not None:
        chapter_block = _build_chapter_block(*chapter_ctx)
        prompt = (
            f"{chapter_list_block}\n\n---\n\n"
            f"{chapter_block}\n\n---\n\n"
            f"{source_context}\n\nConversation:\n{conversation}"
        )
    else:
        prompt = f"{chapter_list_block}\n\n---\n\n{source_context}\n\nConversation:\n{conversation}"

    async for chunk in _run_agent_stream(_QA_INSTRUCTION, prompt):
        yield chunk


async def stream_socratic_response(
    messages: list[ChatMessage],
    topic_id: uuid.UUID,
    session: AsyncSession,
    chapter_id: uuid.UUID | None = None,
) -> AsyncIterator[str]:
    """Stream a Socratic response — one question at a time, never corrects directly."""
    logger.info("stream_socratic_response: topic_id=%s chapter_id=%s messages=%d", topic_id, chapter_id, len(messages))

    source_ids = await _get_topic_source_ids(session, topic_id)
    chroma_client = get_chroma_client()

    latest_question = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )

    if source_ids:
        chunk_pairs = query_topic_chunks_with_sources(
            chroma_client, source_ids, latest_question, n_results=6, max_distance=1.1
        )
        logger.debug("stream_socratic_response: retrieved %d chunks", len(chunk_pairs))
    else:
        chunk_pairs = []
        logger.info("stream_socratic_response: no source material for topic_id=%s", topic_id)

    chapter_ctx = None
    if chapter_id is not None:
        chapter_ctx = await _get_chapter_context(session, chapter_id)
        logger.debug("stream_socratic_response: chapter_ctx fetched=%s", chapter_ctx is not None)

    if not chunk_pairs and chapter_ctx is None:
        yield (
            "I don't have source material for this topic yet. "
            "Please add sources before starting a Socratic session."
        )
        return

    source_context = _build_source_context(chunk_pairs)
    conversation = _build_conversation_prompt(messages)

    if chapter_ctx is not None:
        chapter_block = _build_chapter_block(*chapter_ctx)
        prompt = (
            f"{chapter_block}\n\n---\n\n{source_context}\n\n"
            f"Conversation so far:\n{conversation}\n\nAsk your next Socratic question."
        )
    else:
        prompt = (
            f"{source_context}\n\nConversation so far:\n{conversation}"
            "\n\nAsk your next Socratic question."
        )

    async for chunk in _run_agent_stream(_SOCRATIC_INSTRUCTION, prompt):
        yield chunk


async def stream_expand_response(
    messages: list[ChatMessage],
    topic_id: uuid.UUID,
    session: AsyncSession,
    chapter_id: uuid.UUID | None = None,
) -> AsyncIterator[str]:
    """Stream an enriched content expansion response."""
    logger.info("stream_expand_response: topic_id=%s chapter_id=%s messages=%d", topic_id, chapter_id, len(messages))

    source_ids = await _get_topic_source_ids(session, topic_id)
    chroma_client = get_chroma_client()

    concept = next((m.content for m in reversed(messages) if m.role == "user"), "")

    if source_ids:
        chunk_pairs = query_topic_chunks_with_sources(
            chroma_client, source_ids, concept, n_results=8, max_distance=1.1
        )
        logger.debug("stream_expand_response: retrieved %d chunks", len(chunk_pairs))
    else:
        chunk_pairs = []
        logger.info("stream_expand_response: no source material for topic_id=%s", topic_id)

    chapter_ctx = None
    if chapter_id is not None:
        chapter_ctx = await _get_chapter_context(session, chapter_id)
        logger.debug("stream_expand_response: chapter_ctx fetched=%s", chapter_ctx is not None)

    if not chunk_pairs and chapter_ctx is None:
        yield (
            "I don't have source material for this topic yet. "
            "Please add sources before requesting content expansion."
        )
        return

    source_context = _build_source_context(chunk_pairs)

    if chapter_ctx is not None:
        chapter_block = _build_chapter_block(*chapter_ctx)
        prompt = f"{chapter_block}\n\n---\n\n{source_context}\n\nStudent request: {concept}"
    else:
        prompt = f"{source_context}\n\nStudent request: {concept}"

    async for chunk in _run_agent_stream(_EXPAND_INSTRUCTION, prompt):
        yield chunk
