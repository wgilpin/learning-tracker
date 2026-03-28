"""Chapter Scribe: drafts chapters and responds to margin comments."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_chapter_scribe(
    item_id: uuid.UUID,
    item_title: str,
    topic_id: uuid.UUID,
    session: AsyncSession,
) -> str:
    logger.info("Chapter Scribe starting for item_id=%s title=%r", item_id, item_title)
    from documentlm_core.services.chapter import get_context_summaries

    context_summaries = await get_context_summaries(session, topic_id, item_id)
    context = f"\n\n*Prior context*: {context_summaries[0][:100]}…" if context_summaries else ""
    return (
        f"# {item_title}\n\n"
        f"This chapter provides a comprehensive overview of {item_title}.{context}\n\n"
        "## Introduction\n\nThis is placeholder content generated without an LLM.\n\n"
        "## Core Concepts\n\nKey concepts will be elaborated here.\n\n"
        "## Summary\n\nThis chapter covered the essentials of the topic."
    )


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
    if chapter_result.scalar_one_or_none() is None:
        raise ValueError(f"AtomicChapter {chapter_id} not found")

    return (
        f"Thank you for your question regarding: '{comment.content[:80]}'. "
        "This is a clarifying response from the Chapter Scribe."
    )
