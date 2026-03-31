"""Integration tests for source intake and bibliography routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_sources_returns_200(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Sources Test"))
    response = await test_client.get(f"/topics/{topic.id}/sources")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bibliography_returns_200(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Bibliography Test"))
    response = await test_client.get(
        f"/topics/{topic.id}/bibliography",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_appears_in_bibliography(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    from documentlm_core.schemas import SourceCreate, TopicCreate
    from documentlm_core.services.source import create_source
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Bib Test"))
    await create_source(
        async_session,
        SourceCreate(topic_id=topic.id, doi="10.1234/bib", title="My Source", authors=[]),
    )

    response = await test_client.get(
        f"/topics/{topic.id}/bibliography",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "My Source" in response.text
