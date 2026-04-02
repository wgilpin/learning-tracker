# learning-tracker Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-01

## Active Technologies
- Python 3.12 via uv workspaces + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google ADK, ChromaDB (new), nlp_utils (local) (003-source-extraction-pipeline)
- PostgreSQL (Docker) for source records and status; ChromaDB (Docker) for chunk vectors (003-source-extraction-pipeline)
- Python 3.12 (uv workspaces) + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, HTMX, `bcrypt>=4.1` (new), `starlette.middleware.sessions` (already present via Starlette) (004-multi-user-isolation)
- PostgreSQL 16 (Docker) — new tables: `users`, `invitation_codes`, `user_source_refs`; modified: `topics` (add `user_id`), `sources` (remove `topic_id`, global unique `content_hash`). ChromaDB — collection topology changes from per-topic to per-source. (004-multi-user-isolation)
- Python 3.12 via `uv` workspaces + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google Gemini (via `google-generativeai`), HTMX (005-syllabus-chapter-management)
- PostgreSQL 16 (Docker) — existing `syllabus_items` table (005-syllabus-chapter-management)

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
- 005-syllabus-chapter-management: Added Python 3.12 via `uv` workspaces + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google Gemini (via `google-generativeai`), HTMX
- 004-multi-user-isolation: Added Python 3.12 (uv workspaces) + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, HTMX, `bcrypt>=4.1` (new), `starlette.middleware.sessions` (already present via Starlette)
- 003-source-extraction-pipeline: Added Python 3.12 via uv workspaces + FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google ADK, ChromaDB (new), nlp_utils (local)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
