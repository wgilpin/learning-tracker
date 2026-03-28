"""Integration tests for chapter routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chapter_draft_blocked_returns_409(test_client: AsyncClient, async_session) -> None:
    """POST /syllabus-items/{id}/chapter returns 409 when parent has no chapter."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="409 Test"))
    parent = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="Parent")
    )
    child = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Child", parent_id=parent.id),
    )

    response = await test_client.post(
        f"/syllabus-items/{child.id}/chapter",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chapter_draft_no_parent_returns_200(
    test_client: AsyncClient, async_session
) -> None:
    """POST /syllabus-items/{id}/chapter returns 200 for a root item (no parent)."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Root Item Test"))
    item = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="No Parent")
    )

    response = await test_client.post(
        f"/syllabus-items/{item.id}/chapter",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chapter_not_found_returns_404(test_client: AsyncClient) -> None:
    response = await test_client.get(f"/chapters/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chapter_status_pending_for_missing(test_client: AsyncClient) -> None:
    response = await test_client.get(f"/chapters/{uuid.uuid4()}/status")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
