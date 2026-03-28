from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from typing import cast

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from documentlm_core.db.models import Base

# Alembic Config object
config = context.config

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url with DATABASE_URL env var if set
_db_url: str = cast(
    str,
    os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url")),
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without a DB connection."""
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = create_async_engine(_db_url)
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
