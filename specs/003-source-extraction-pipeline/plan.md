# Implementation Plan: Source Extraction Pipeline

**Branch**: `003-source-extraction-pipeline` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-source-extraction-pipeline/spec.md`

## Summary

Every source associated with a topic — regardless of type or how it was added — is extracted, chunked, and upserted into a per-topic ChromaDB collection immediately as a background task. When the Chapter Scribe generates a chapter, it first queries ChromaDB for the top-10 most relevant chunks (~5,000 chars) scoped to the syllabus item's title, then uses that material as grounding context in its prompt.

## Technical Context

**Language/Version**: Python 3.12 via uv workspaces
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google ADK, ChromaDB (new), nlp_utils (local)
**Storage**: PostgreSQL (Docker) for source records and status; ChromaDB embedded persistent client for chunk vectors (no separate service)
**Testing**: pytest + pytest-asyncio; ChromaDB ephemeral client in tests; HTTP calls mocked via pytest-mock
**Target Platform**: Docker Compose (local dev + demo)
**Project Type**: Web service (FastAPI + HTMX)
**Performance Goals**: Background extraction completes without blocking the UI; chapter generation adds <2s overhead for ChromaDB retrieval
**Constraints**: Top-10 chunks, ~500 chars each (~5,000 chars) max context per chapter call
**Scale/Scope**: Prototype; tens of sources per topic, hundreds of chunks per collection

## Constitution Check

| Principle | Gate Question | Status |
|-----------|---------------|--------|
| I. Test-First | ChromaDB ephemeral client in tests; extraction HTTP calls mocked; LLM calls mocked | ✅ |
| II. Strong Typing | All new functions fully annotated; `IndexStatus` StrEnum; no `Any`, no bare `dict` | ✅ |
| III. Simplicity | Single `extract_and_index_source` function; no abstractions beyond spec requirements | ✅ |
| IV. Functional Style | Pipeline is a pure async function; DB and ChromaDB writes pushed to edges | ✅ |
| V. Logging | Each pipeline step logged; all exceptions caught, logged with traceback, status → FAILED | ✅ |
| Tech Stack | Python/uv, FastAPI, HTMX, PostgreSQL+Docker; ChromaDB embedded persistent client (no extra service) | ✅ |
| Quality Gates | ruff + mypy + pytest all pass; no `Any`, no bare `dict` signatures | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/003-source-extraction-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
packages/documentlm-core/src/documentlm_core/
├── config.py                                         # add chroma_url
├── db/
│   ├── models.py                                     # add index_status, index_error, content to Source
│   └── migrations/versions/
│       └── 0003_add_source_index_fields.py
├── schemas.py                                        # add IndexStatus; update SourceRead
└── services/
    ├── chroma.py                                     # NEW — ChromaDB client functions
    ├── pipeline.py                                   # NEW — extract_and_index_source()
    └── source.py                                     # minor: primary_only filter
agents/
    ├── academic_scout.py                             # call pipeline after source created
    └── chapter_scribe.py                             # prepend ChromaDB context to prompt

apps/api/src/api/templates/sources/
└── _row.html                                         # add index_status badge

docker-compose.yml                                    # NEW — postgres + chroma services

tests/
├── unit/test_pipeline.py                             # mocked extraction + chroma
├── unit/test_chroma_service.py                       # ephemeral chroma client
└── integration/test_pipeline_integration.py         # real PG + ephemeral chroma
```

**Structure Decision**: All new logic in `documentlm-core`. No new packages. ChromaDB runs embedded (in-process, persistent client) — no extra Docker service. No vector columns in PostgreSQL — all chunk/embedding storage delegated to ChromaDB.
