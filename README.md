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

# Run migrations
uv run alembic upgrade head

# Start the app
uv run uvicorn api.main:app --reload
```

## Creating the first user

Access is invitation-only. To create a user:

1. Generate an invite code:

   ```bash
   uv run --project apps/api python -m api.cli invite
   ```

   This prints a code like `INV-abc123...`

2. Open `/register` in the browser and enter the code, email, and password.

## Operator CLI

```bash
# Generate an invitation code
uv run --project apps/api python -m api.cli invite

# Reset a user's password
uv run --project apps/api python -m api.cli reset-password user@example.com newpassword

# Deactivate a user account
uv run --project apps/api python -m api.cli deactivate-user user@example.com
```

## Running tests

```bash
# All tests
uv run pytest

# API integration tests only
uv run pytest apps/api/tests/integration/ -m integration
```
