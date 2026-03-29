# Quickstart: Academic Learning Tracker

**Branch**: `001-academic-learning-tracker`
**Date**: 2026-03-28

---

## Prerequisites

- Docker + Docker Compose (v2)
- `uv` (Python package manager) — install via `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.12+ (managed by `uv`, no separate install needed)
- Google AI API key (for ADK agents)

---

## 1. Clone & Install

```bash
git clone <repo-url>
cd learning-tracker
uv sync --all-packages
```

This installs all workspace packages (`documentlm-core`, `apps/api`) and their dependencies
into a shared virtual environment at `.venv/`.

---

## 2. Configure Environment

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Required variables:

```bash
# Database (matches docker-compose.yml defaults)
DATABASE_URL=postgresql+asyncpg://tracker:tracker@localhost:5432/tracker

# Google ADK
GOOGLE_API_KEY=<your-google-ai-api-key>

# Application
LOG_LEVEL=INFO
```

---

## 3. Start Infrastructure

```bash
docker compose up -d
```

This starts:
- `db` — PostgreSQL 16 with `pgvector` extension, exposed on port `5432`
- Data is persisted in a named volume `postgres_data`

Verify the DB is ready:

```bash
docker compose ps
# db should show "healthy"
```

---

## 4. Run Migrations

```bash
uv run alembic upgrade head
```

This creates all tables (Topics, SyllabusItems, AtomicChapters, Sources, etc.) and enables
the `pgvector` extension.

---

## 5. Start the Application

**Development** (hot-reload):

```bash
uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Via Docker Compose** (full stack):

```bash
docker compose --profile app up
```

The app is available at `http://localhost:8000`.

---

## 6. Smoke Test

```bash
# Run all tests (DB must be running)
uv run pytest

# Run only unit tests (no DB required)
uv run pytest -m unit

# Run with coverage
uv run pytest --cov=packages/documentlm_core --cov=apps/api
```

All tests MUST pass before proceeding with any feature work.

---

## 7. Code Quality Checks

Run before every commit:

```bash
# Linting + formatting
uv run ruff check .
uv run ruff format .

# Type checking
uv run mypy packages/ apps/
```

All three MUST exit with code 0.

---

## 8. Create a First Topic (Manual Validation)

1. Open `http://localhost:8000` in a browser.
2. Click **New Topic** and enter "Introduction to Neural Networks".
3. Wait for the Syllabus Architect to generate the syllabus (progress bar will update).
4. Verify the syllabus appears with concept nodes in dependency order.
5. Navigate to the source queue and add a source manually if needed.
6. Select an unblocked node, click **Draft Chapter**, and wait for the Chapter Scribe.
7. Read the chapter and add a margin comment.
8. View the Bibliography tab — the cited source should appear.

---

## Common Issues

| Symptom | Fix |
|---------|-----|
| `asyncpg.exceptions.ConnectionDoesNotExistError` | PostgreSQL not running — `docker compose up -d db` |
| `ERROR: relation "topics" does not exist` | Migrations not applied — `uv run alembic upgrade head` |
| ADK agent returns empty response | Check `GOOGLE_API_KEY` in `.env` |
| `mypy` errors on first run | Run `uv sync` to ensure stubs are installed |
