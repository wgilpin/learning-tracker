"""Integration tests for per-user topic and content isolation (US3).

Tests are written FIRST (TDD). They must FAIL until T029-T033 are implemented.
"""

from __future__ import annotations

import json
import uuid
from base64 import b64encode

import itsdangerous
import pytest
import pytest_asyncio
from documentlm_core.config import settings
from documentlm_core.db.session import get_session
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _make_session_cookie(user_id: uuid.UUID) -> str:
    signer = itsdangerous.TimestampSigner(settings.session_secret_key)
    payload = b64encode(json.dumps({"user_id": str(user_id)}).encode()).decode()
    return signer.sign(payload).decode()


@pytest_asyncio.fixture
async def user_b(async_session: AsyncSession):
    """A second active user (user B) within the same test transaction."""
    from documentlm_core.auth import hash_password
    from documentlm_core.db.models import User

    user = User(
        id=uuid.uuid4(),
        email="user_b@example.com",
        password_hash=hash_password("password_b"),
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest_asyncio.fixture
async def client_b(test_engine, async_session: AsyncSession, user_b) -> AsyncClient:
    """AsyncClient authenticated as user_b, sharing the same DB session."""
    from api.main import create_app

    app = create_app()

    async def override_get_session():
        yield async_session

    app.dependency_overrides[get_session] = override_get_session

    session_cookie = _make_session_cookie(user_b.id)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"session": session_cookie},
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# T024 — Topic isolation
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_topic_isolation_list_empty_for_other_user(
    test_client: AsyncClient,
    client_b: AsyncClient,
    async_session: AsyncSession,
    test_user,
) -> None:
    """User B's topic list is empty even though user A has a topic."""
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    await create_topic(async_session, TopicCreate(title="User A Topic"), user_id=test_user.id)
    await async_session.flush()

    # User B lists topics — must see an empty list
    resp_b = await client_b.get("/")
    assert resp_b.status_code == 200
    assert "User A Topic" not in resp_b.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_topic_isolation_get_returns_404_for_other_user(
    test_client: AsyncClient,
    client_b: AsyncClient,
    async_session: AsyncSession,
    test_user,
) -> None:
    """User B gets 404 when accessing user A's topic by ID."""
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Private Topic"), user_id=test_user.id)
    await async_session.flush()

    # User B attempts to access it directly — must be 404 (not 403)
    resp = await client_b.get(f"/topics/{topic.id}")
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_topic_isolation_delete_returns_404_for_other_user(
    test_client: AsyncClient,
    client_b: AsyncClient,
    async_session: AsyncSession,
    test_user,
) -> None:
    """User B gets 404 when attempting to delete user A's topic."""
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Protected Topic"), user_id=test_user.id)
    await async_session.flush()

    resp = await client_b.delete(f"/topics/{topic.id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# T025 — Child content isolation (syllabus items)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_child_isolation_syllabus_inaccessible(
    test_client: AsyncClient,
    client_b: AsyncClient,
    async_session: AsyncSession,
    test_user,
) -> None:
    """User B cannot access the syllabus panel of user A's topic."""
    from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(
        async_session, TopicCreate(title="A's Topic with Items"), user_id=test_user.id
    )
    await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Chapter 1"),
    )
    await async_session.flush()

    # User B tries to fetch the syllabus panel — must 404
    resp = await client_b.get(
        f"/topics/{topic.id}/syllabus",
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_child_isolation_sources_inaccessible(
    test_client: AsyncClient,
    client_b: AsyncClient,
    async_session: AsyncSession,
    test_user,
) -> None:
    """User B cannot access the sources page of user A's topic."""
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="A's Topic"), user_id=test_user.id)
    await async_session.flush()

    resp = await client_b.get(f"/topics/{topic.id}/sources")
    assert resp.status_code == 404
