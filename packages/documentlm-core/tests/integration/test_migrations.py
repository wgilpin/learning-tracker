"""Verify that Alembic migrations apply cleanly."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
