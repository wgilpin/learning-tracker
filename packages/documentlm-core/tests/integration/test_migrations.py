"""Verify that Alembic migrations apply cleanly and pgvector extension is present."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pgvector_extension_exists(async_session: AsyncSession) -> None:
    result = await async_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    )
    row = result.fetchone()
    assert row is not None, "pgvector extension must be installed"
    assert row[0] == "vector"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_tables_exist(async_session: AsyncSession) -> None:
    expected_tables = {
        "topics",
        "syllabus_items",
        "sources",
        "atomic_chapters",
        "chapter_sources",
        "margin_comments",
    }
    result = await async_session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    existing = {row[0] for row in result.fetchall()}
    missing = expected_tables - existing
    assert not missing, f"Missing tables: {missing}"
