"""Integration tests for syllabus CRUD endpoints (US1–US4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# US1: POST /topics/{topic_id}/syllabus-items
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_syllabus_item_happy_path(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """POST with title + description creates item and returns _child_item.html fragment."""
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US1 Happy Path Topic"), user_id=test_user.id
    )

    response = await test_client.post(
        f"/topics/{topic.id}/syllabus-items",
        data={"title": "Introduction", "description": "An intro chapter."},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Introduction" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_syllabus_item_empty_title_returns_422(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """POST with empty title returns 422 with an error fragment."""
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US1 422 Topic"), user_id=test_user.id
    )

    response = await test_client.post(
        f"/topics/{topic.id}/syllabus-items",
        data={"title": "   ", "description": ""},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_syllabus_item_duplicate_title_returns_item_and_warning(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """POST with duplicate title returns 200 with item row and warning banner."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US1 Duplicate Topic"), user_id=test_user.id
    )
    await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Existing Chapter"),
    )

    response = await test_client.post(
        f"/topics/{topic.id}/syllabus-items",
        data={"title": "Existing Chapter", "description": ""},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Existing Chapter" in response.text
    body = response.text.lower()
    assert "duplicate" in body or "already exists" in body or "warning" in body


# ---------------------------------------------------------------------------
# US2: POST /syllabus-items/{item_id}/generate-description
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_description_returns_populated_textarea(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """POST generate-description returns a textarea fragment with generated text on success."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US2 Generate Topic"), user_id=test_user.id
    )
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Photosynthesis"),
    )

    generated = "Photosynthesis is the process by which plants convert light into energy."
    with patch(
        "api.routers.syllabus.generate_item_description",
        new=AsyncMock(return_value=generated),
    ):
        response = await test_client.post(
            f"/syllabus-items/{item.id}/generate-description",
            data={"title": "Photosynthesis"},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert "textarea" in response.text.lower()
    assert "Photosynthesis is the process" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_description_gemini_failure_returns_503(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """POST generate-description returns 503 error fragment when Gemini fails."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US2 Fail Topic"), user_id=test_user.id
    )
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Mitosis"),
    )

    with patch(
        "api.routers.syllabus.generate_item_description",
        new=AsyncMock(side_effect=RuntimeError("Gemini unavailable")),
    ):
        response = await test_client.post(
            f"/syllabus-items/{item.id}/generate-description",
            data={"title": "Mitosis"},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# US3: PATCH /syllabus-items/{item_id}
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_syllabus_item_happy_path(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """PATCH with a new title returns updated _child_item.html row."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US3 PATCH Topic"), user_id=test_user.id
    )
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Old Title"),
    )

    response = await test_client.patch(
        f"/syllabus-items/{item.id}",
        data={"title": "New Title"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "New Title" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_syllabus_item_empty_title_returns_422(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """PATCH with empty title returns 422."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US3 422 Topic"), user_id=test_user.id
    )
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="A Chapter"),
    )

    response = await test_client.patch(
        f"/syllabus-items/{item.id}",
        data={"title": "   "},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_syllabus_item_duplicate_title_returns_warning(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """PATCH with duplicate title returns 200 with item row + warning."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US3 Duplicate Topic"), user_id=test_user.id
    )
    await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Sibling Chapter"),
    )
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="My Chapter"),
    )

    response = await test_client.patch(
        f"/syllabus-items/{item.id}",
        data={"title": "Sibling Chapter"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Sibling Chapter" in response.text
    body = response.text.lower()
    assert "duplicate" in body or "already exists" in body or "warning" in body


# ---------------------------------------------------------------------------
# US4: DELETE /syllabus-items/{item_id}
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_syllabus_item_success(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """DELETE removes the item and returns 200."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item, list_syllabus_items
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="US4 Delete Topic"), user_id=test_user.id
    )
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="To Be Deleted"),
    )

    response = await test_client.delete(
        f"/syllabus-items/{item.id}",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    items = await list_syllabus_items(async_session, topic.id)
    assert not any(i.id == item.id for i in items)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_confirm_shows_associated_content_warning(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """GET delete-confirm shows 'has associated content' warning for items with children."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session,
        TopicCreate(title="US4 Confirm Content Topic"),
        user_id=test_user.id,
    )
    parent = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Parent Chapter"),
    )
    await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Child Chapter", parent_id=parent.id),
    )

    response = await test_client.get(
        f"/syllabus-items/{parent.id}/delete-confirm",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    body = response.text.lower()
    assert "associated" in body or "content" in body or "children" in body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_confirm_shows_last_chapter_warning(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    """GET delete-confirm shows empty-syllabus warning when deleting the last item."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session,
        TopicCreate(title="US4 Last Chapter Topic"),
        user_id=test_user.id,
    )
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Only Chapter"),
    )

    response = await test_client.get(
        f"/syllabus-items/{item.id}/delete-confirm",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    body = response.text.lower()
    assert "last" in body or "empty" in body or "only" in body
