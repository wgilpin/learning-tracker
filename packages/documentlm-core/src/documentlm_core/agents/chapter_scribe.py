"""Chapter Scribe: drafts chapters and responds to margin comments using Gemini."""

from __future__ import annotations

import logging
import uuid

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.config import settings

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

If prior chapter summaries are provided, briefly acknowledge how this topic builds on them.

Write only the chapter content — no preamble, no "here is your chapter" introductions.
"""

_COMMENT_INSTRUCTION = """You are an academic tutor responding to a student's question or comment on a passage they are reading.

The student has highlighted a paragraph and asked a question or left a note.
Provide a clear, helpful response that:
- Directly addresses what the student asked or noted
- Explains or expands on the concept if they seem confused
- Keeps the response concise (2-4 sentences) unless the question warrants more depth

Respond only with the answer — no preamble.
"""


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
) -> str:
    logger.info("Chapter Scribe starting for item_id=%s title=%r", item_id, item_title)
    from documentlm_core.services.chapter import get_context_summaries

    context_summaries = await get_context_summaries(session, topic_id, item_id)

    prompt_parts = [f"Topic: {item_title}"]
    if context_summaries:
        summaries_text = "\n".join(f"- {s}" for s in context_summaries)
        prompt_parts.append(f"Prior chapters in this topic (for context):\n{summaries_text}")
    prompt_parts.append("Write the chapter now.")

    content = await _run_agent(_CHAPTER_INSTRUCTION, "\n\n".join(prompt_parts))
    logger.info("Chapter Scribe complete for item_id=%s", item_id)
    return content


async def respond_to_comment(
    comment_id: uuid.UUID,
    chapter_id: uuid.UUID,
    session: AsyncSession,
) -> str:
    logger.info("Chapter Scribe responding to comment_id=%s", comment_id)
    from sqlalchemy import select

    from documentlm_core.db.models import AtomicChapter, MarginComment

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

    prompt = (
        f"The student is reading a chapter. They highlighted the following paragraph:\n\n"
        f"[Paragraph anchor: {comment.paragraph_anchor}]\n\n"
        f"Their comment or question:\n{comment.content}\n\n"
        f"Chapter excerpt for context (first 500 chars):\n{chapter.content[:500]}"
    )

    response = await _run_agent(_COMMENT_INSTRUCTION, prompt)
    logger.info("Chapter Scribe comment response complete for comment_id=%s", comment_id)
    return response
