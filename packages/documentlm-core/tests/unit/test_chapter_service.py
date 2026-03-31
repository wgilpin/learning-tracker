"""Unit tests for chapter service."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from documentlm_core.schemas import IndexStatus, SourceType


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
async def test_create_chapter_links_verified_source() -> None:
    """create_chapter only creates ChapterSource rows for VERIFIED sources."""
    from documentlm_core.services.chapter import create_chapter

    item_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    source_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    mock_item = MagicMock()
    mock_item.id = item_id
    mock_item.parent_id = None

    item_result = MagicMock()
    item_result.scalar_one_or_none.return_value = mock_item

    no_chapter_result = MagicMock()
    no_chapter_result.scalar_one_or_none.return_value = None

    # Source fetch for verified guard
    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.verification_status = "VERIFIED"
    mock_source.source_type = "SEARCH"
    mock_source.is_primary = False
    mock_source.index_status = "INDEXED"
    mock_source.index_error = None
    mock_source.url = "https://example.com"
    mock_source.doi = None
    mock_source.title = "Test Source"
    mock_source.authors = []
    mock_source.publication_date = None
    mock_source.content = None
    mock_source.topic_id = topic_id

    source_fetch_result = MagicMock()
    source_fetch_result.scalars.return_value.all.return_value = [mock_source]

    empty_source_result = MagicMock()
    empty_source_result.scalars.return_value.all.return_value = []

    empty_comment_result = MagicMock()
    empty_comment_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(
        side_effect=[
            item_result,
            no_chapter_result,
            source_fetch_result,  # verified guard fetch
            empty_source_result,  # _read_chapter sources
            empty_comment_result,
        ]
    )

    result = await create_chapter(mock_session, item_id, topic_id, "content", [source_id])
    assert result.content == "content"
    # session.add called at least twice: chapter + ChapterSource
    assert mock_session.add.call_count >= 2
