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
        selected_text=data.selected_text,
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


async def resolve_and_apply(
    session: AsyncSession,
    comment_id: uuid.UUID,
) -> uuid.UUID:
    """Resolve a comment and splice its response into the chapter after the anchored paragraph.

    Returns the chapter_id so the caller can re-render the chapter.
    """
    from datetime import UTC, datetime

    comment = await _get_or_raise(session, comment_id)
    if not comment.response:
        raise ValueError(f"Comment {comment_id} has no response to apply")

    # Extract paragraph index (1-based) from anchor like "para-<uuid>-N"
    para_index = int(comment.paragraph_anchor.rsplit("-", 1)[1])

    chapter_result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == comment.chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    if chapter is None:
        raise ValueError(f"AtomicChapter {comment.chapter_id} not found")

    paragraphs = chapter.content.split("\n\n")
    para_block = paragraphs[para_index - 1] if para_index <= len(paragraphs) else ""

    if comment.selected_text and comment.selected_text.strip() in para_block:
        # Find the line within the block that contains the selected text and insert after it
        lines = para_block.split("\n")
        insert_line = len(lines)  # default: after block
        for i, line in enumerate(lines):
            if comment.selected_text.strip() in line:
                insert_line = i + 1
                break
        lines.insert(insert_line, "")
        lines.insert(insert_line + 1, comment.response)
        paragraphs[para_index - 1] = "\n".join(lines)
    else:
        # Fall back: insert as a new paragraph after the block
        insert_at = min(para_index, len(paragraphs))
        paragraphs.insert(insert_at, comment.response)

    chapter.content = "\n\n".join(paragraphs)
    chapter.updated_at = datetime.now(UTC)

    comment.status = CommentStatus.RESOLVED.value
    comment.resolved_at = datetime.now(UTC)
    await session.flush()
    logger.info(
        "Applied and resolved comment_id=%s into chapter_id=%s after paragraph %d",
        comment_id,
        chapter.id,
        para_index,
    )
    return chapter.id


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
