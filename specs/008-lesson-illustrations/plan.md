# Implementation Plan: Lesson Illustrations

**Branch**: `008-lesson-illustrations` | **Date**: 2026-04-04 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/008-lesson-illustrations/spec.md`

## Summary

After a chapter is generated, the system automatically assesses each paragraph with a text LLM to determine whether it would benefit from an illustration, then calls a configurable Gemini image-generation model to produce simple academic-style images (no background, no overlay text) for those paragraphs. Images are stored in a new `chapter_illustrations` PostgreSQL table and served via a new FastAPI endpoint. Chapter templates are updated to render `<img>` tags inline below illustrated paragraphs. Failures in the pipeline never block chapter rendering.

## Technical Context

**Language/Version**: Python 3.12+ (uv workspaces monorepo)  
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Google ADK (`google-adk`), `google.genai` (transitive via ADK)  
**Storage**: PostgreSQL 16 (Docker) — new `chapter_illustrations` table with `bytea` image column  
**Testing**: pytest (unit with mocked LLM calls; integration against real Dockerised PostgreSQL)  
**Target Platform**: Linux server (Docker container)  
**Project Type**: web-service  
**Performance Goals**: Illustration pipeline runs in background; chapter rendering unblocked  
**Constraints**: Illustration failures must never surface to the student; pipeline is best-effort  
**Scale/Scope**: Prototype — a few users, chapters up to ~20 paragraphs, images < 500KB each  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Question | Status |
| --------- | ------------- | ------ |
| I. Test-First | Are tests scoped to local infra only (no live LLM/remote API calls)? | ✅ All LLM calls mocked in unit tests; integration tests target real local PostgreSQL only |
| II. Strong Typing | Do all new functions have fully annotated signatures? No `Any`, no bare `dict`? | ✅ All new schemas use `BaseModel`/`dataclass`; `ParagraphAssessment` typed; image bytes typed as `bytes` |
| III. Simplicity | Is this the simplest implementation satisfying the spec? No unapproved scope? | ✅ bytea storage avoids file-system dependency; single new endpoint; no caching layer |
| IV. Functional Style | Is side-effectful code pushed to the edges? No inheritance for reuse? | ✅ Pure assessment/generation functions; DB writes isolated in `services/illustration.py` |
| V. Logging | Does every exception boundary log with traceback? No silent failures? | ✅ Each pipeline stage wrapped with logger.exception(); chapter rendering never raises |
| Tech Stack | Python/uv, FastAPI, HTMX, PostgreSQL+Docker, no raw JS framework? | ✅ No new dependencies outside existing stack + `google.genai` (already transitive) |
| Quality Gates | ruff + mypy + pytest all pass? No `Any`, no bare `dict` signatures? | ✅ Enforced per task completion criteria |

## Project Structure

### Documentation (this feature)

```text
specs/008-lesson-illustrations/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── illustration-endpoint.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not created by /speckit.plan)
```

### Source Code

```text
packages/documentlm-core/src/documentlm_core/
├── config.py                            # +illustration_model field
├── schemas.py                           # +ParagraphAssessment, IllustrationRead
├── db/
│   └── models.py                        # +ChapterIllustration ORM model
├── agents/
│   ├── chapter_scribe.py               # (existing, unchanged)
│   ├── illustration_assessor.py        # NEW — assess paragraph via text LLM
│   └── image_generator.py              # NEW — generate image via google.genai
└── services/
    └── illustration.py                 # NEW — orchestrate assess→generate→persist

packages/documentlm-core/
└── alembic/versions/
    └── <hash>_add_chapter_illustrations.py  # NEW migration

apps/api/src/api/
├── routers/
│   └── chapters.py                     # +illustration endpoint, +pipeline trigger
└── templates/chapters/
    ├── detail.html                     # +<img> rendering per paragraph
    └── _inline.html                    # +<img> rendering per paragraph

tests/
├── unit/
│   ├── test_illustration_assessor.py   # NEW — mock LLM, test JSON parsing + edge cases
│   ├── test_image_generator.py         # NEW — mock google.genai, test byte extraction
│   └── test_illustration_service.py   # NEW — mock assessor + generator, test orchestration
└── integration/
    └── test_illustration_db.py         # NEW — real PostgreSQL, test persist + fetch
```

**Structure Decision**: Single-project layout (Option 1). No new packages; all illustration logic lives in the existing `documentlm-core` package as new modules under `agents/` and `services/`. The `api` app gets a new endpoint and updated templates only.

## Complexity Tracking

> No constitution violations requiring justification.
