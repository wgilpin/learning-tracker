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

_QA_INSTRUCTION = """You are a knowledgeable academic tutor answering questions about a topic.

You are given numbered source excerpts and a conversation history.
Answer the student's question directly and naturally — do NOT open with phrases like
"Based on the provided source material" or "According to the source material".
If you cite a specific excerpt, use inline notation like "According to [2]..." or just "[2]".
If the excerpts do not cover the question, say so honestly — do not fabricate.
Keep answers clear and concise. Use markdown for structure when helpful.
"""

_SOCRATIC_INSTRUCTION = """You are a Socratic tutor helping a student develop their understanding.

Rules:
- Ask exactly ONE question at a time — never multiple questions in one response.
- Never directly correct the student or give away the answer.
- Follow the student's answer closely: probe the gap in their understanding, not a script.
- If the student demonstrates clear understanding of the concept, advance to a harder question or
  acknowledge mastery.
- Base your questions on the numbered source excerpts provided.
- Keep your response focused: one question, briefly framed.
"""

_EXPAND_INSTRUCTION = """You are an academic tutor providing enriched explanations.

The student wants to explore a concept more deeply.
Extract the key concept from their message and provide a richer, more detailed explanation
drawing on the numbered source excerpts.
If the excerpts do not cover the concept, say so and offer what you can from general
knowledge, clearly labelling it as such.

Use markdown for structure. Be thorough but not padded.
"""


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
    return f"Source excerpts:\n\n{numbered}"


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
) -> AsyncIterator[str]:
    """Stream a Q&A response using ChromaDB context and conversation history."""
    logger.info("stream_qa_response: topic_id=%s messages=%d", topic_id, len(messages))

    source_ids = await _get_topic_source_ids(session, topic_id)
    chroma_client = get_chroma_client()

    latest_question = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )

    if source_ids:
        chunk_pairs = query_topic_chunks_with_sources(
            chroma_client, source_ids, latest_question, n_results=6
        )
        logger.debug("stream_qa_response: retrieved %d chunks from ChromaDB", len(chunk_pairs))
    else:
        chunk_pairs = []
        logger.info("stream_qa_response: no source material for topic_id=%s", topic_id)

    if not chunk_pairs:
        yield (
            "I don't have any source material for this topic yet. "
            "Please add some sources first so I can answer questions based on the material."
        )
        return

    source_context = _build_source_context(chunk_pairs)
    conversation = _build_conversation_prompt(messages)
    prompt = f"{source_context}\n\nConversation:\n{conversation}"

    async for chunk in _run_agent_stream(_QA_INSTRUCTION, prompt):
        yield chunk


async def stream_socratic_response(
    messages: list[ChatMessage],
    topic_id: uuid.UUID,
    session: AsyncSession,
) -> AsyncIterator[str]:
    """Stream a Socratic response — one question at a time, never corrects directly."""
    logger.info("stream_socratic_response: topic_id=%s messages=%d", topic_id, len(messages))

    source_ids = await _get_topic_source_ids(session, topic_id)
    chroma_client = get_chroma_client()

    latest_question = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )

    if source_ids:
        chunk_pairs = query_topic_chunks_with_sources(
            chroma_client, source_ids, latest_question, n_results=6
        )
        logger.debug("stream_socratic_response: retrieved %d chunks", len(chunk_pairs))
    else:
        chunk_pairs = []
        logger.info("stream_socratic_response: no source material for topic_id=%s", topic_id)

    if not chunk_pairs:
        yield (
            "I don't have source material for this topic yet. "
            "Please add sources before starting a Socratic session."
        )
        return

    source_context = _build_source_context(chunk_pairs)
    conversation = _build_conversation_prompt(messages)
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
) -> AsyncIterator[str]:
    """Stream an enriched content expansion response."""
    logger.info("stream_expand_response: topic_id=%s messages=%d", topic_id, len(messages))

    source_ids = await _get_topic_source_ids(session, topic_id)
    chroma_client = get_chroma_client()

    concept = next((m.content for m in reversed(messages) if m.role == "user"), "")

    if source_ids:
        chunk_pairs = query_topic_chunks_with_sources(
            chroma_client, source_ids, concept, n_results=8
        )
        logger.debug("stream_expand_response: retrieved %d chunks", len(chunk_pairs))
    else:
        chunk_pairs = []
        logger.info("stream_expand_response: no source material for topic_id=%s", topic_id)

    if not chunk_pairs:
        yield (
            "I don't have source material for this topic yet. "
            "Please add sources before requesting content expansion."
        )
        return

    source_context = _build_source_context(chunk_pairs)
    prompt = f"{source_context}\n\nStudent request: {concept}"

    async for chunk in _run_agent_stream(_EXPAND_INSTRUCTION, prompt):
        yield chunk
