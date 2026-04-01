"""Integration tests for source intake and bibliography routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_sources_returns_200(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Sources Test"), user_id=test_user.id)
    response = await test_client.get(f"/topics/{topic.id}/sources")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bibliography_returns_200(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Bibliography Test"), user_id=test_user.id)
    response = await test_client.get(
        f"/topics/{topic.id}/bibliography",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_appears_in_bibliography(
    test_client: AsyncClient, async_session: AsyncSession, test_user
) -> None:
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.source import add_source_for_user, compute_content_hash
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Bib Test"), user_id=test_user.id)
    content = "My Source document content"
    await add_source_for_user(
        async_session,
        user_id=test_user.id,
        topic_id=topic.id,
        title="My Source",
        content=content,
        content_hash=compute_content_hash(content),
    )
    await async_session.flush()

    response = await test_client.get(
        f"/topics/{topic.id}/bibliography",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "My Source" in response.text
