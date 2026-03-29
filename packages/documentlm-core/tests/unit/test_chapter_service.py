"""Unit tests for chapter service: parent blocking check, citation guard."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from documentlm_core.schemas import IndexStatus, SourceStatus, SourceType


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_chapter_raises_when_item_not_found() -> None:
    """create_chapter raises ValueError when SyllabusItem does not exist."""
    from documentlm_core.services.chapter import create_chapter

    item_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    mock_session = AsyncMock()
    item_result = MagicMock()
    item_result.scalar_one_or_none.return_value = None  # item not found
    mock_session.execute = AsyncMock(return_value=item_result)

    with pytest.raises(ValueError):
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

    empty_comment_result = MagicMock()
    empty_comment_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(
        side_effect=[item_result, no_chapter_result, empty_source_result, empty_comment_result]
    )

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
        source_type=SourceType.SEARCH,
        is_primary=False,
        index_status=IndexStatus.PENDING,
        index_error=None,
        url="https://a.com",
        doi=None,
        title="A",
        authors=[],
        publication_date=None,
        verification_status=SourceStatus.QUEUED,
        content=None,
    )
    verified = SourceRead(
        id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        source_type=SourceType.SEARCH,
        is_primary=False,
        index_status=IndexStatus.INDEXED,
        index_error=None,
        url="https://b.com",
        doi=None,
        title="B",
        authors=[],
        publication_date=None,
        verification_status=SourceStatus.VERIFIED,
        content=None,
    )

    filtered = _filter_verified_sources([queued, verified])
    assert len(filtered) == 1
    assert filtered[0].id == verified.id
