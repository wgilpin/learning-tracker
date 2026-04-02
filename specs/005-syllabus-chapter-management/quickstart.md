# Quickstart: Syllabus Chapter Management

**Branch**: `005-syllabus-chapter-management` | **Date**: 2026-04-01

## Prerequisites

- Docker and `docker compose` running (PostgreSQL + app containers)
- `uv` installed
- `GOOGLE_API_KEY` set in environment (or `.env` file)

## Running the Stack

```bash
docker compose up -d          # start PostgreSQL
cd apps/api
uv run uvicorn api.main:app --reload
```

## Running Tests

```bash
# From repo root — runs all tests including new integration tests
cd packages/documentlm-core
uv run pytest tests/ -v

# Run only tests for this feature
uv run pytest tests/services/test_syllabus_crud.py -v
```

## Manual Smoke Test

1. Log in at `http://localhost:8000`
2. Open any existing topic → the syllabus panel is visible
3. **Add chapter with description**: click "Add chapter", fill in title + description, submit → row appears at bottom of list
4. **Add chapter without description**: click "Add chapter", fill title only, click "Generate description" → textarea populates with AI-generated text; accept or edit; submit → row appears
5. **Add with duplicate title**: enter a title that already exists → warning banner appears above the form; submitting again saves the duplicate
6. **Edit chapter**: click edit icon on a row → row becomes an edit form; modify title or description; save → row returns to read mode with updated values
7. **Delete chapter (with content)**: click delete on a chapter that has been drafted → confirmation shows "this chapter has associated content" warning; confirm → row removed
8. **Delete last chapter**: delete all chapters until one remains; click delete → confirmation shows empty-syllabus warning; confirm → syllabus is empty

## Quality Gates

```bash
# Must all pass before marking any task complete
uv run ruff check .
uv run mypy packages/documentlm-core/src --strict
uv run pytest
```
