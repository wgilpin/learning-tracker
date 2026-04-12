# Learning Tracker

A personal academic learning tracker. Server-rendered with FastAPI + HTMX.

## Stack

- Python 3.12, uv workspaces
- FastAPI + HTMX + Jinja2
- PostgreSQL + ChromaDB
- Google Gemini (chapter generation)

## Setup

```bash
# Install dependencies
uv sync

# Start services (PostgreSQL + ChromaDB)
docker compose up -d

# Run schema migrations
uv run alembic upgrade head

# Start the app
uv run uvicorn api.main:app --reload
```

## Creating the first user

Access is invitation-only. To create a user:

1. Generate an invite code:

   ```bash
   uv run manage invite
   ```

   This prints a code like `INV-abc123...`

2. Open `/register` in the browser and enter the code, email, and password.

## Operator CLI

```bash
# Generate an invitation code
uv run manage invite

# Reset a user's password
uv run manage reset-password user@example.com newpassword

# Deactivate a user account
uv run manage deactivate-user user@example.com
```

## Data migrations

Some features backfill AI-generated content (e.g. learning objectives) for existing records without
regenerating expensive content like syllabi or illustrations. Run them with `./data_migrate.sh`
(see Deployment below). Each migration is idempotent and records itself in the `data_migrations`
table once complete.

To see what migration files exist locally:

```bash
uv run manage migrate-data --list
```

### Adding a new data migration

Create a numbered file in `packages/documentlm-core/src/documentlm_core/data_migrations/`:

```python
# 002_your_migration_name.py
description = "What this migration does"

async def run(session: AsyncSession) -> int:
    # ... query, update, return count of rows processed
    return count
```

The runner discovers files by sorted filename, skips already-applied ones, and commits after each.

## Deployment (OrbStack)

```bash
./deploy_prod.sh       # build and restart all services
./alembic_migrate.sh   # run schema migrations (Alembic) in the container
./data_migrate.sh      # run data migrations (backfills) in the container
```

Schema migrations also run automatically on container startup (via `CMD` in `Dockerfile.api`).

## Running tests

```bash
# All tests
uv run pytest

# API integration tests only
uv run pytest apps/api/tests/integration/ -m integration
```
