"""MarginComment service: create, attach agent response, resolve."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import AtomicChapter, MarginComment
from documentlm_core.schemas import CommentStatus, MarginCommentCreate, MarginCommentRead

logger = logging.getLogger(__name__)


async def create_comment(
    session: AsyncSession,
    chapter_id: uuid.UUID,
    data: MarginCommentCreate,
) -> MarginCommentRead:
    # Verify chapter exists
    chapter_result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    if chapter_result.scalar_one_or_none() is None:
        raise ValueError(f"AtomicChapter {chapter_id} not found")

    comment = MarginComment(
        id=uuid.uuid4(),
        chapter_id=chapter_id,
        paragraph_anchor=data.paragraph_anchor,
        content=data.content,
        response=None,
        status=CommentStatus.OPEN.value,
        created_at=datetime.now(UTC),
    )
    session.add(comment)
    await session.flush()
    logger.info("Created margin comment id=%s chapter_id=%s", comment.id, chapter_id)
    return _to_read(comment)


async def attach_response(
    session: AsyncSession,
    comment_id: uuid.UUID,
    response_text: str,
) -> MarginCommentRead:
    comment = await _get_or_raise(session, comment_id)
    comment.response = response_text
    await session.flush()
    logger.info("Attached response to comment_id=%s", comment_id)
    return _to_read(comment)


async def resolve_comment(
    session: AsyncSession,
    comment_id: uuid.UUID,
) -> MarginCommentRead:
    comment = await _get_or_raise(session, comment_id)
    comment.status = CommentStatus.RESOLVED.value
    comment.resolved_at = datetime.now(UTC)
    await session.flush()
    logger.info("Resolved comment_id=%s", comment_id)
    return _to_read(comment)


async def _get_or_raise(session: AsyncSession, comment_id: uuid.UUID) -> MarginComment:
    result = await session.execute(select(MarginComment).where(MarginComment.id == comment_id))
    comment = result.scalar_one_or_none()
    if comment is None:
        raise ValueError(f"MarginComment {comment_id} not found")
    return comment


def _to_read(comment: MarginComment) -> MarginCommentRead:
    return MarginCommentRead(
        id=comment.id,
        chapter_id=comment.chapter_id,
        paragraph_anchor=comment.paragraph_anchor,
        content=comment.content,
        response=comment.response,
        status=CommentStatus(comment.status),
        created_at=comment.created_at,
    )
