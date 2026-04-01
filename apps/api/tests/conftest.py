from __future__ import annotations

import json
import os
import uuid
from base64 import b64encode
from collections.abc import AsyncGenerator

import itsdangerous
import pytest_asyncio
from documentlm_core.config import settings
from documentlm_core.db.models import Base
from documentlm_core.db.session import get_session
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tracker:tracker@localhost:5432/tracker",
)


def _make_session_cookie(user_id: uuid.UUID) -> str:
    """Return a signed session cookie value that Starlette's SessionMiddleware accepts."""
    signer = itsdangerous.TimestampSigner(settings.session_secret_key)
    payload = b64encode(json.dumps({"user_id": str(user_id)}).encode()).decode()
    return signer.sign(payload).decode()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    # Use a single connection with an outer transaction that never commits.
    # join_transaction_mode="create_savepoint" means any session.commit() inside
    # handlers creates a SAVEPOINT (not a real commit), so the outer rollback
    # undoes everything including all handler commits.
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        yield session
        await conn.rollback()


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession):
    """A pre-created active user available within the test transaction."""
    from documentlm_core.auth import hash_password
    from documentlm_core.db.models import User

    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        password_hash=hash_password("testpassword"),
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest_asyncio.fixture
async def test_client(test_engine, async_session: AsyncSession, test_user) -> AsyncClient:
    """AsyncClient authenticated as test_user, DB session overridden to test transaction."""
    from api.main import create_app

    app = create_app()

    async def override_get_session():
        yield async_session

    app.dependency_overrides[get_session] = override_get_session

    session_cookie = _make_session_cookie(test_user.id)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"session": session_cookie},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def unauth_client(test_engine, async_session: AsyncSession) -> AsyncClient:
    """AsyncClient with no session cookie — for testing unauthenticated flows."""
    from api.main import create_app

    app = create_app()

    async def override_get_session():
        yield async_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
