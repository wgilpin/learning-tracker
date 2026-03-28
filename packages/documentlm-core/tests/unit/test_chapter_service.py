"""Unit tests for chapter service: parent blocking check, citation guard."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from documentlm_core.schemas import SourceStatus


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_chapter_blocked_when_parent_has_no_chapter() -> None:
    """chapter service raises ValueError when parent item has no chapter yet."""
    from documentlm_core.services.chapter import create_chapter

    item_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    mock_item = MagicMock()
    mock_item.id = item_id
    mock_item.parent_id = parent_id

    item_result = MagicMock()
    item_result.scalar_one_or_none.return_value = mock_item

    no_parent_chapter = MagicMock()
    no_parent_chapter.scalar_one_or_none.return_value = None

    mock_session.execute = AsyncMock(side_effect=[item_result, no_parent_chapter])

    with pytest.raises(ValueError, match="parent"):
        await create_chapter(mock_session, item_id, topic_id, "content", [])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_chapter_succeeds_for_root_item() -> None:
    """Chapter creation succeeds for a root item (no parent)."""
    from documentlm_core.services.chapter import create_chapter

    item_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    mock_item = MagicMock()
    mock_item.id = item_id
    mock_item.parent_id = None

    item_result = MagicMock()
    item_result.scalar_one_or_none.return_value = mock_item

    no_chapter_result = MagicMock()
    no_chapter_result.scalar_one_or_none.return_value = None

    empty_source_result = MagicMock()
    empty_source_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[item_result, no_chapter_result, empty_source_result])

    result = await create_chapter(mock_session, item_id, topic_id, "Chapter content", [])
    assert result.content == "Chapter content"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_citation_only_verified_sources() -> None:
    """Only VERIFIED sources may be cited in a chapter."""
    from documentlm_core.schemas import SourceRead
    from documentlm_core.services.chapter import _filter_verified_sources

    queued = SourceRead(
        id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        url="https://a.com",
        doi=None,
        title="A",
        authors=[],
        publication_date=None,
        verification_status=SourceStatus.QUEUED,
    )
    verified = SourceRead(
        id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        url="https://b.com",
        doi=None,
        title="B",
        authors=[],
        publication_date=None,
        verification_status=SourceStatus.VERIFIED,
    )

    filtered = _filter_verified_sources([queued, verified])
    assert len(filtered) == 1
    assert filtered[0].id == verified.id
