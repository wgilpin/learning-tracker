"""Unit tests for syllabus service CRUD functions (US2–US4)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# US2: generate_item_description
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_item_description_success() -> None:
    """generate_item_description returns Gemini text on success."""
    from documentlm_core.services.syllabus import generate_item_description

    topic_id = uuid.uuid4()

    sibling_result = MagicMock()
    sibling_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=sibling_result)

    mock_response = MagicMock()
    mock_response.text = "A clear description of the chapter."

    with patch(
        "documentlm_core.services.syllabus._get_genai_client"
    ) as mock_client_factory:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_client_factory.return_value = mock_client

        result = await generate_item_description(mock_session, topic_id, None, "Chapter Title")

    assert result == "A clear description of the chapter."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_item_description_gemini_failure_raises_runtime_error() -> None:
    """generate_item_description raises RuntimeError when Gemini call fails."""
    from documentlm_core.services.syllabus import generate_item_description

    topic_id = uuid.uuid4()

    sibling_result = MagicMock()
    sibling_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=sibling_result)

    with patch(
        "documentlm_core.services.syllabus._get_genai_client"
    ) as mock_client_factory:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("Network error")
        )
        mock_client_factory.return_value = mock_client

        with pytest.raises(RuntimeError):
            await generate_item_description(mock_session, topic_id, None, "Chapter Title")


# ---------------------------------------------------------------------------
# US3: update_syllabus_item
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_syllabus_item_title() -> None:
    """update_syllabus_item updates title and returns updated read schema."""
    from documentlm_core.schemas import SyllabusItemUpdate
    from documentlm_core.services.syllabus import update_syllabus_item

    item_id = uuid.uuid4()

    mock_item = MagicMock()
    mock_item.id = item_id
    mock_item.topic_id = uuid.uuid4()
    mock_item.parent_id = None
    mock_item.title = "Old Title"
    mock_item.description = None
    mock_item.status = "UNRESEARCHED"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_item

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=result_mock)

    updated = await update_syllabus_item(
        mock_session, item_id, SyllabusItemUpdate(title="New Title")
    )

    assert updated.title == "New Title"
    assert mock_item.title == "New Title"
    mock_session.flush.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_syllabus_item_description() -> None:
    """update_syllabus_item updates description independently."""
    from documentlm_core.schemas import SyllabusItemUpdate
    from documentlm_core.services.syllabus import update_syllabus_item

    item_id = uuid.uuid4()

    mock_item = MagicMock()
    mock_item.id = item_id
    mock_item.topic_id = uuid.uuid4()
    mock_item.parent_id = None
    mock_item.title = "My Chapter"
    mock_item.description = None
    mock_item.status = "UNRESEARCHED"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_item

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=result_mock)

    updated = await update_syllabus_item(
        mock_session, item_id, SyllabusItemUpdate(description="New description")
    )

    assert updated.description == "New description"
    assert mock_item.description == "New description"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_syllabus_item_empty_title_raises_value_error() -> None:
    """update_syllabus_item raises ValueError when title becomes empty after strip."""
    from documentlm_core.schemas import SyllabusItemUpdate
    from documentlm_core.services.syllabus import update_syllabus_item

    item_id = uuid.uuid4()

    mock_item = MagicMock()
    mock_item.id = item_id
    mock_item.topic_id = uuid.uuid4()
    mock_item.parent_id = None
    mock_item.title = "Chapter"
    mock_item.description = None
    mock_item.status = "UNRESEARCHED"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_item

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="empty"):
        await update_syllabus_item(
            mock_session, item_id, SyllabusItemUpdate(title="   ")
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_syllabus_item_not_found_raises_value_error() -> None:
    """update_syllabus_item raises ValueError when item does not exist."""
    from documentlm_core.schemas import SyllabusItemUpdate
    from documentlm_core.services.syllabus import update_syllabus_item

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError):
        await update_syllabus_item(
            mock_session, uuid.uuid4(), SyllabusItemUpdate(title="Anything")
        )


# ---------------------------------------------------------------------------
# US4: has_associated_content + delete_syllabus_item
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_has_associated_content_true_when_has_children() -> None:
    """has_associated_content returns True when item has child items."""
    from documentlm_core.services.syllabus import has_associated_content

    item_id = uuid.uuid4()

    # First execute: no chapter; second execute: has a child
    no_chapter = MagicMock()
    no_chapter.scalar_one_or_none.return_value = None
    has_child = MagicMock()
    has_child.scalar_one_or_none.return_value = MagicMock()  # a child exists

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[no_chapter, has_child])

    result = await has_associated_content(mock_session, item_id)
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_has_associated_content_true_when_has_chapter() -> None:
    """has_associated_content returns True when item has a linked AtomicChapter."""
    from documentlm_core.services.syllabus import has_associated_content

    item_id = uuid.uuid4()

    # First execute: chapter found → returns True immediately
    has_chapter = MagicMock()
    has_chapter.scalar_one_or_none.return_value = MagicMock()

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=has_chapter)

    result = await has_associated_content(mock_session, item_id)
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_has_associated_content_false_when_empty() -> None:
    """has_associated_content returns False when no chapter or children."""
    from documentlm_core.services.syllabus import has_associated_content

    item_id = uuid.uuid4()

    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=empty)

    result = await has_associated_content(mock_session, item_id)
    assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_syllabus_item_happy_path() -> None:
    """delete_syllabus_item calls session.delete on found item."""
    from documentlm_core.services.syllabus import delete_syllabus_item

    item_id = uuid.uuid4()
    mock_item = MagicMock()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_item

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=result_mock)

    await delete_syllabus_item(mock_session, item_id)

    mock_session.delete.assert_called_once_with(mock_item)
    mock_session.flush.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_syllabus_item_not_found_raises_value_error() -> None:
    """delete_syllabus_item raises ValueError when item does not exist."""
    from documentlm_core.services.syllabus import delete_syllabus_item

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError):
        await delete_syllabus_item(mock_session, uuid.uuid4())
