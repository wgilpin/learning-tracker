"""Unit tests for margin comment service: create, resolve, response attachment."""

from __future__ import annotations

import uuid
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from documentlm_core.schemas import CommentStatus, MarginCommentCreate


def _make_orm_comment(
    *,
    comment_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    status: str = "OPEN",
    response: str | None = None,
) -> MagicMock:
    m = MagicMock()
    m.id = comment_id or uuid.uuid4()
    m.chapter_id = chapter_id or uuid.uuid4()
    m.paragraph_anchor = "para-1"
    m.content = "What does this mean?"
    m.response = response
    m.status = status
    from datetime import datetime

    m.created_at = datetime.now(UTC)
    m.resolved_at = None
    return m


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_comment_returns_open_status() -> None:
    from documentlm_core.services.margin_comment import create_comment

    chapter_id = uuid.uuid4()
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Mock chapter existence check
    chapter_result = MagicMock()
    mock_chapter = MagicMock()
    mock_chapter.id = chapter_id
    chapter_result.scalar_one_or_none.return_value = mock_chapter
    mock_session.execute = AsyncMock(return_value=chapter_result)

    comment = await create_comment(
        mock_session,
        chapter_id,
        MarginCommentCreate(paragraph_anchor="para-1", content="What does this mean?"),
    )

    assert comment.status == CommentStatus.OPEN
    assert comment.chapter_id == chapter_id
    assert comment.paragraph_anchor == "para-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_comment_sets_resolved_status() -> None:
    from documentlm_core.services.margin_comment import resolve_comment

    comment_id = uuid.uuid4()
    mock_orm = _make_orm_comment(comment_id=comment_id, status="OPEN")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_orm
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await resolve_comment(mock_session, comment_id)
    assert mock_orm.status == "RESOLVED"
    assert result.status == CommentStatus.RESOLVED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_attach_response_sets_response_text() -> None:
    from documentlm_core.services.margin_comment import attach_response

    comment_id = uuid.uuid4()
    mock_orm = _make_orm_comment(comment_id=comment_id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_orm
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await attach_response(mock_session, comment_id, "Here is the explanation.")
    assert mock_orm.response == "Here is the explanation."
    assert result.response == "Here is the explanation."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_comment_not_found_raises() -> None:
    from documentlm_core.services.margin_comment import resolve_comment

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValueError, match="not found"):
        await resolve_comment(mock_session, uuid.uuid4())
