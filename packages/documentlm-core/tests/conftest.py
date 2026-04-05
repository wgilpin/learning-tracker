from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from documentlm_core.db.models import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tracker:tracker@localhost:5434/tracker_test",
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session that rolls back after each test."""
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await session.begin()
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def db_rollback(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Alias for async_session — explicit rollback fixture."""
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await session.begin()
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession):
    """A pre-created active user for tests that need a topic owner."""
    import uuid

    import bcrypt
    from documentlm_core.db.models import User

    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        password_hash=bcrypt.hashpw(b"testpassword", bcrypt.gensalt(rounds=4)).decode(),
    )
    async_session.add(user)
    await async_session.flush()
    return user
