"""Integration tests for PATCH /syllabus-items/{id}/status."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_status_updates_item(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Status Router Test"), user_id=test_user.id)
    item = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="Item A")
    )

    response = await test_client.patch(
        f"/syllabus-items/{item.id}/status",
        data={"status": "IN_PROGRESS"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    # Template renders the item; IN_PROGRESS shows without the is-done class
    assert str(item.id) in response.text
    assert "is-done" not in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_status_mastered(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    from documentlm_core.schemas import SyllabusItemCreate, SyllabusStatus, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item, list_syllabus_items
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Mastered Test"), user_id=test_user.id)
    item = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="Section 1")
    )

    await test_client.patch(
        f"/syllabus-items/{item.id}/status",
        data={"status": "MASTERED"},
        headers={"HX-Request": "true"},
    )

    items = await list_syllabus_items(async_session, topic.id)
    updated = next(i for i in items if i.id == item.id)
    assert updated.status == SyllabusStatus.MASTERED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_status_invalid_value_returns_422(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="422 Test"), user_id=test_user.id)
    item = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="Item")
    )

    response = await test_client.patch(
        f"/syllabus-items/{item.id}/status",
        data={"status": "INVALID"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_status_not_found_returns_404(test_client: AsyncClient) -> None:
    response = await test_client.patch(
        f"/syllabus-items/{uuid.uuid4()}/status",
        data={"status": "MASTERED"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 404
