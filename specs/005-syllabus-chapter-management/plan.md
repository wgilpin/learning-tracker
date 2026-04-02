# Implementation Plan: Syllabus Chapter Management

**Branch**: `005-syllabus-chapter-management` | **Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-syllabus-chapter-management/spec.md`

## Summary

Add full CRUD management for `SyllabusItem` records (referred to as "chapters" in the UI). The existing system creates syllabus items only via bulk AI generation at topic-creation time. This feature adds individual create, edit, and delete operations directly from the syllabus panel, including a lightweight LLM-powered "Generate description" action for items added without a description. No schema migrations are required — the existing `SyllabusItem` model already carries all needed fields.

## Technical Context

**Language/Version**: Python 3.12 via `uv` workspaces
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google Gemini (via `google-generativeai`), HTMX
**Storage**: PostgreSQL 16 (Docker) — existing `syllabus_items` table
**Testing**: pytest with async fixtures; real Docker PostgreSQL for integration tests; Gemini mocked in all tests
**Target Platform**: Linux server (Docker); local dev via `docker compose`
**Project Type**: web-service (HTMX + FastAPI server-side rendering)
**Performance Goals**: CRUD operations respond in < 500ms; description generation returns in < 15s (Gemini round-trip)
**Constraints**: No raw JS framework; HTMX only for interactivity; no new DB tables
**Scale/Scope**: Single-user demo/prototype; syllabuses typically 10–50 items

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Question | Status |
|-----------|---------------|--------|
| I. Test-First | Tests written before implementation. LLM (Gemini) is mocked in all tests. Integration tests use real Dockerised PostgreSQL. | ✅ |
| II. Strong Typing | All new service functions and route handlers carry full type annotations. Pydantic models for all new request/response shapes. No `Any`, no bare `dict`. | ✅ |
| III. Simplicity | Three new service functions + four new routes + HTMX templates. No new abstraction layers or configuration points. | ✅ |
| IV. Functional Style | Service functions accept session as argument (pure I/O at edge). No inheritance. No stateful service classes. | ✅ |
| V. Logging | All exception boundaries in new routes and the generation function log with traceback. No silent failures. | ✅ |
| Tech Stack | Python/uv, FastAPI, HTMX, PostgreSQL+Docker, Gemini (existing). No new JS framework or new DB engine. | ✅ |
| Quality Gates | ruff + mypy + pytest all pass. No `Any`, no bare `dict` signatures in new code. | ✅ |

All gates pass. No complexity-tracking violations.

## Project Structure

### Documentation (this feature)

```text
specs/005-syllabus-chapter-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── syllabus-items.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code Changes

```text
packages/documentlm-core/src/documentlm_core/
├── schemas.py                    # + SyllabusItemUpdate, DescriptionGenerateRequest, GeneratedDescriptionRead
├── services/
│   └── syllabus.py               # + update_syllabus_item, delete_syllabus_item, has_associated_content,
│                                 #   generate_item_description
└── db/models.py                  # No changes

apps/api/src/api/
├── routers/
│   └── syllabus.py               # + POST /topics/{topic_id}/syllabus-items
│                                 # + PATCH /syllabus-items/{item_id}
│                                 # + DELETE /syllabus-items/{item_id}
│                                 # + POST /syllabus-items/{item_id}/generate-description
└── templates/
    └── syllabus/
        ├── _child_item.html      # + edit/delete action buttons
        ├── _add_item_form.html   # NEW: inline add form
        ├── _edit_item_form.html  # NEW: inline edit form
        └── _delete_confirm.html  # NEW: inline delete confirmation
```

**Structure Decision**: Single-project layout; all changes confined to existing `documentlm-core` package (service/schema) and `api` app (routes/templates). No new packages or directories.
