# Implementation Plan: Academic Learning Tracker App

**Branch**: `001-academic-learning-tracker` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-academic-learning-tracker/spec.md`

## Summary

Build a source-grounded, AI-driven learning application that generates prerequisite-aware
syllabi for complex topics, drafts deep-dive chapters per concept node using verified academic
sources, tracks learner progress with pedagogical blocking, and supports active reading via
margin comments. The system is a FastAPI + HTMX web app backed by PostgreSQL, with agent
orchestration via Google ADK, implemented as a `uv` monorepo.

## Technical Context

**Language/Version**: Python 3.12 (managed via `uv` workspaces)
**Primary Dependencies**: FastAPI, HTMX, Jinja2, SQLAlchemy 2.x (async), Alembic, Pydantic v2,
  Google ADK (`google-adk`), `pgvector`, `httpx`, `asyncpg`
**Storage**: PostgreSQL 16 with `pgvector` extension in Docker
**Testing**: `pytest` + `pytest-asyncio`; remote API calls (LLMs, ArXiv, YouTube) mocked via
  `unittest.mock` or `pytest-mock`
**Target Platform**: Linux Docker containers (development on macOS/Linux via Docker Compose)
**Project Type**: Web service (FastAPI backend + HTMX server-rendered frontend)
**Performance Goals**: Syllabus generated in <2 min (20 nodes); chapter drafted in <5 min
  (agent-bound, not infrastructure-bound)
**Constraints**: Single-user prototype; online operation assumed; no export, no multi-tenancy
**Scale/Scope**: One learner per topic; prototype with tens of topics and hundreds of chapters

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Question | Status |
| --------- | ------------- | ------ |
| I. Test-First | Are tests scoped to local infra only (no live LLM/remote API calls)? | ✅ |
| II. Strong Typing | Do all new functions have fully annotated signatures? No `Any`, no bare `dict`? | ✅ |
| III. Simplicity | Is this the simplest implementation satisfying the spec? No unapproved scope? | ✅ |
| IV. Functional Style | Is side-effectful code pushed to the edges? No inheritance for reuse? | ✅ |
| V. Logging | Does every exception boundary log with traceback? No silent failures? | ✅ |
| Tech Stack | Python/uv, FastAPI, HTMX, PostgreSQL+Docker, no raw JS framework? | ✅ |
| Quality Gates | ruff + mypy + pytest all pass? No `Any`, no bare `dict` signatures? | ✅ |

**All gates pass.** No complexity violations requiring justification.

*Post-design re-check (Phase 1)*: All gates still pass. ADK agents use typed tool functions;
SQLAlchemy models are separate from Pydantic schemas; DB side effects are at service-layer
edges only.

## Project Structure

### Documentation (this feature)

```text
specs/001-academic-learning-tracker/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── routes.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
packages/
└── documentlm-core/          # Shared engine (uv workspace package)
    ├── src/
    │   └── documentlm_core/
    │       ├── __init__.py
    │       ├── schemas.py         # All Pydantic models (TypedDicts + BaseModels)
    │       ├── db/
    │       │   ├── models.py      # SQLAlchemy ORM models
    │       │   ├── session.py     # Async engine + session factory
    │       │   └── migrations/    # Alembic migration env + versions
    │       ├── services/
    │       │   ├── topic.py       # Topic CRUD
    │       │   ├── syllabus.py    # SyllabusItem CRUD + blocking logic + cycle detection
    │       │   ├── chapter.py     # Chapter CRUD + context folding
    │       │   ├── source.py      # Source CRUD + deduplication
    │       │   └── bibliography.py  # Aggregation query
    │       └── agents/
    │           ├── syllabus_architect.py   # ADK Agent: syllabus generation
    │           ├── academic_scout.py       # ADK Agent: source discovery
    │           └── chapter_scribe.py       # ADK Agent: chapter drafting + margin responses
    └── tests/
        ├── unit/                  # Pure function tests (no DB, no ADK)
        └── integration/           # Tests against real PostgreSQL (Docker)

apps/
└── api/                          # FastAPI application (uv workspace package)
    ├── src/
    │   └── api/
    │       ├── main.py            # App factory + lifespan
    │       ├── routers/
    │       │   ├── topics.py
    │       │   ├── syllabus.py
    │       │   ├── chapters.py
    │       │   ├── sources.py
    │       │   └── bibliography.py
    │       ├── templates/         # Jinja2 HTML templates
    │       │   ├── base.html
    │       │   ├── topics/
    │       │   ├── syllabus/
    │       │   ├── chapters/
    │       │   └── sources/
    │       └── static/            # CSS only; no JS bundles
    └── tests/
        └── integration/           # FastAPI TestClient + real DB

docker/
├── compose.yml                    # Full stack: db + api services
├── Dockerfile.api                 # Production image for apps/api
└── postgres/
    └── init.sql                   # CREATE EXTENSION vector;

pyproject.toml                     # uv workspace root
.env.example
alembic.ini
```

**Structure Decision**: `uv` workspace with `packages/documentlm-core` (shared logic) and
`apps/api` (HTTP layer). PostgreSQL + pgvector in a single Docker container; API server in a
second container. All agent logic lives in `documentlm-core`; `apps/api` only handles HTTP
routing and template rendering.

## Complexity Tracking

> No violations — constitution gates all pass.
