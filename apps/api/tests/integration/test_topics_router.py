"""Integration tests for topic and syllabus routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_root_returns_200(test_client: AsyncClient) -> None:
    response = await test_client.get("/")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_topics_creates_topic(test_client: AsyncClient) -> None:
    response = await test_client.post(
        "/topics",
        data={"title": "Introduction to Neural Networks"},
        follow_redirects=False,
    )
    # Should redirect to /topics/{id}
    assert response.status_code in (302, 303)
    assert "/topics/" in response.headers.get("location", "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_topics_missing_title_returns_422(test_client: AsyncClient) -> None:
    response = await test_client.post("/topics", data={})
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_topic_not_found_returns_404(test_client: AsyncClient) -> None:
    response = await test_client.get(f"/topics/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_topic_detail(test_client: AsyncClient) -> None:
    # Create a topic first
    post = await test_client.post("/topics", data={"title": "Graph Theory"}, follow_redirects=False)
    location = post.headers["location"]
    topic_id = location.split("/topics/")[1].rstrip("/")

    response = await test_client.get(f"/topics/{topic_id}")
    assert response.status_code == 200
    assert "Graph Theory" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_syllabus_returns_partial(
    test_client: AsyncClient, async_session
) -> None:
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Calculus"))

    response = await test_client.get(
        f"/topics/{topic.id}/syllabus",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_topic_status_endpoint(test_client: AsyncClient, async_session) -> None:
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Status Test"))

    response = await test_client.get(f"/topics/{topic.id}/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "item_count" in data
