"""Integration tests for margin comment routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_chapter(async_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Helper: create topic + unblocked item + chapter."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.chapter import create_chapter
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Comment Test Topic"))
    item = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="Unblocked Item")
    )
    chapter = await create_chapter(async_session, item.id, topic.id, "Some content.", [])
    return chapter.id, item.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_comment_returns_200(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    chapter_id, _ = await _create_chapter(async_session)

    response = await test_client.post(
        f"/chapters/{chapter_id}/comments",
        data={"paragraph_anchor": "para-1", "content": "What does this mean?"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_comment_invalid_chapter_returns_404(test_client: AsyncClient) -> None:
    response = await test_client.post(
        f"/chapters/{uuid.uuid4()}/comments",
        data={"paragraph_anchor": "para-1", "content": "Question"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_comment_returns_200(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    from documentlm_core.schemas import MarginCommentCreate
    from documentlm_core.services.margin_comment import create_comment

    chapter_id, _ = await _create_chapter(async_session)
    comment = await create_comment(
        async_session, chapter_id, MarginCommentCreate(paragraph_anchor="para-1", content="Q?")
    )

    response = await test_client.patch(
        f"/comments/{comment.id}/resolve",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_nonexistent_comment_returns_404(test_client: AsyncClient) -> None:
    response = await test_client.patch(
        f"/comments/{uuid.uuid4()}/resolve",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 404
