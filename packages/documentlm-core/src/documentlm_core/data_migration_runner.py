"""Data migration runner.

Discovers and applies numbered data migrations from the
documentlm_core/data_migrations/ directory.

Each migration file must define:
    description: str          — human-readable summary shown in output
    async def run(session: AsyncSession) -> int:
        ...                   — performs the migration; returns count of items processed.
                                May commit internally for large batches — all migrations
                                MUST be idempotent so they can be safely re-run.

Usage (via the manage CLI):
    uv run manage migrate-data [--list] [--run NAME]

Tracking table: `data_migrations` (created by Alembic migration 0018).
"""

from __future__ import annotations

import importlib.util
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "data_migrations"


def _discover() -> list[Path]:
    """Return migration files sorted by name, excluding __init__ and private files."""
    return sorted(
        p for p in _MIGRATIONS_DIR.glob("*.py")
        if not p.name.startswith("_")
    )


def _load(path: Path):
    """Import a migration module from its file path."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migration: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


async def _applied_names(session: AsyncSession) -> set[str]:
    result = await session.execute(text("SELECT name FROM data_migrations ORDER BY name"))
    return {row[0] for row in result.fetchall()}


async def _record(session: AsyncSession, name: str) -> None:
    await session.execute(
        text("INSERT INTO data_migrations (name, applied_at) VALUES (:name, :at)"),
        {"name": name, "at": datetime.now(UTC)},
    )


def list_migrations() -> None:
    """Print all migration files. No DB connection required."""
    paths = _discover()
    if not paths:
        print("No data migrations found.", flush=True)
        return
    for path in paths:
        mod = _load(path)
        desc = getattr(mod, "description", "(no description)")
        print(f"  {path.stem}  —  {desc}", flush=True)


async def run_migrations(session: AsyncSession, *, name: str | None = None) -> None:
    """Run all pending migrations, or a single named migration.

    Args:
        session: An async DB session. The runner commits after recording each
                 migration; individual migrations may also commit mid-run for
                 large batches.
        name: If given, run only that migration (by stem name, e.g.
              '001_backfill_learning_objectives'). Raises ValueError if unknown.
    """
    paths = _discover()
    print(f"Discovered {len(paths)} migration(s) in {_MIGRATIONS_DIR}", flush=True)

    if name is not None:
        matches = [p for p in paths if p.stem == name]
        if not matches:
            raise ValueError(
                f"Migration {name!r} not found. "
                f"Available: {[p.stem for p in paths]}"
            )
        paths = matches

    applied = await _applied_names(session)
    pending = [p for p in paths if p.stem not in applied]

    if not pending:
        print("Nothing to migrate — all migrations already applied.", flush=True)
        return

    print(f"{len(pending)} pending: {[p.stem for p in pending]}", flush=True)

    for path in pending:
        mod = _load(path)
        desc = getattr(mod, "description", "(no description)")
        print(f"Running  {path.stem}  —  {desc}", flush=True)

        try:
            count = await mod.run(session)
            await _record(session, path.stem)
            await session.commit()
            print(f"  → done ({count} item(s) processed)", flush=True)
        except Exception:
            await session.rollback()
            logger.exception("Data migration %s failed — rolled back", path.stem)
            print("  ✗ failed — see logs for details", flush=True)
            raise
