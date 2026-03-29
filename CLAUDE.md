# learning-tracker Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-29

## Active Technologies
- Python 3.12 via uv workspaces + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google ADK, ChromaDB (new), nlp_utils (local) (003-source-extraction-pipeline)
- PostgreSQL (Docker) for source records and status; ChromaDB (Docker) for chunk vectors (003-source-extraction-pipeline)

- Python 3.12 (managed via `uv` workspaces) + FastAPI, HTMX, Jinja2, SQLAlchemy 2.x (async), Alembic, Pydantic v2, (001-academic-learning-tracker)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.12 (managed via `uv` workspaces): Follow standard conventions

## Recent Changes
- 003-source-extraction-pipeline: Added Python 3.12 via uv workspaces + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google ADK, ChromaDB (new), nlp_utils (local)

- 001-academic-learning-tracker: Added Python 3.12 (managed via `uv` workspaces) + FastAPI, HTMX, Jinja2, SQLAlchemy 2.x (async), Alembic, Pydantic v2,

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
