"""Integration tests for source queue and bibliography routes."""

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
async def test_verify_source_updates_status(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    from documentlm_core.schemas import SourceCreate, TopicCreate
    from documentlm_core.services.source import create_source
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Verify Test"))
    source = await create_source(
        async_session,
        SourceCreate(
            topic_id=topic.id,
            doi="10.1234/verify-test",
            title="Test Paper",
            authors=["Author A"],
        ),
    )

    response = await test_client.patch(f"/sources/{source.id}/verify")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reject_source_updates_status(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    from documentlm_core.schemas import SourceCreate, TopicCreate
    from documentlm_core.services.source import create_source
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Reject Test"))
    source = await create_source(
        async_session,
        SourceCreate(
            topic_id=topic.id,
            doi="10.1234/reject-test",
            title="Bad Paper",
            authors=["Author B"],
        ),
    )

    response = await test_client.patch(f"/sources/{source.id}/reject")
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
async def test_verified_source_appears_in_bibliography(
    test_client: AsyncClient, async_session: AsyncSession
) -> None:
    """Verified source appears in bibliography; unverified does not."""
    from documentlm_core.schemas import SourceCreate, TopicCreate
    from documentlm_core.services.source import create_source, verify_source
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Bib Test"))
    source = await create_source(
        async_session,
        SourceCreate(topic_id=topic.id, doi="10.1234/bib", title="Verified Source", authors=[]),
    )
    await verify_source(async_session, source.id)
    await create_source(
        async_session,
        SourceCreate(topic_id=topic.id, url="https://unverified.com", title="Unverified", authors=[]),
    )

    response = await test_client.get(
        f"/topics/{topic.id}/bibliography",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "Verified Source" in response.text
    assert "Unverified" not in response.text
