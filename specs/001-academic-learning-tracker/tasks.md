---

description: "Task list for Academic Learning Tracker App implementation"
---

# Tasks: Academic Learning Tracker App

**Input**: Design documents from `/specs/001-academic-learning-tracker/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/routes.md ✅

**Tests**: Included — TDD is mandated by the project constitution (Principle I) for all backend
services and code.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing. Each story produces a complete, independently testable increment.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths included in every task description

## Path Conventions

- Shared engine: `packages/documentlm_core/src/documentlm_core/`
- Web app: `apps/api/src/api/`
- Engine tests: `packages/documentlm_core/tests/`
- API tests: `apps/api/tests/`

---

## Phase 1: Setup (Project Initialisation)

**Purpose**: `uv` workspace scaffolding, Docker infrastructure, tooling config.

- [X] T001 Create root `pyproject.toml` defining the `uv` workspace with members `packages/documentlm-core` and `apps/api`
- [X] T002 [P] Create `packages/documentlm-core/pyproject.toml` with dependencies: `sqlalchemy[asyncio]`, `alembic`, `pydantic`, `pgvector`, `asyncpg`, `httpx`, `google-adk`; dev deps: `pytest`, `pytest-asyncio`, `pytest-mock`, `mypy`, `ruff`
- [X] T003 [P] Create `apps/api/pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`; dev deps: `httpx`, `pytest`, `pytest-asyncio`
- [X] T004 [P] Create `docker/compose.yml` defining `db` service (postgres:16 + pgvector, port 5432, named volume `postgres_data`, health check) and `api` service profile
- [X] T005 [P] Create `docker/postgres/init.sql` with `CREATE EXTENSION IF NOT EXISTS vector;`
- [X] T006 [P] Create `docker/Dockerfile.api` for production image of `apps/api`
- [X] T007 [P] Create `.env.example` with `DATABASE_URL`, `GOOGLE_API_KEY`, `LOG_LEVEL`
- [X] T008 [P] Create `alembic.ini` pointing to `packages/documentlm_core/src/documentlm_core/db/migrations/` and configure `ruff` + `mypy` sections in root `pyproject.toml`

**Checkpoint**: `uv sync --all-packages` succeeds; `docker compose up -d` starts a healthy DB.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB session, all ORM models, Pydantic schemas, Alembic migrations, FastAPI app
factory, Source CRUD, and test fixtures. ALL user story work blocks on this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T009 Create async DB engine + `AsyncSession` factory in `packages/documentlm_core/src/documentlm_core/db/session.py`
- [X] T010 Create `packages/documentlm_core/src/documentlm_core/schemas.py` with all enums (`SyllabusStatus`, `SourceStatus`, `CommentStatus`) and all Pydantic `BaseModel` schemas from data-model.md (`TopicCreate`, `TopicRead`, `SyllabusItemCreate`, `SyllabusItemRead`, `SyllabusItemStatusUpdate`, `SourceCreate`, `SourceRead`, `ChapterRead`, `MarginCommentCreate`, `MarginCommentRead`)
- [X] T011 [P] Create SQLAlchemy ORM models `Topic` and `VirtualBook` in `packages/documentlm_core/src/documentlm_core/db/models.py`
- [X] T012 [P] Add SQLAlchemy ORM models `SyllabusItem` and `SyllabusPrerequisite` to `packages/documentlm_core/src/documentlm_core/db/models.py`
- [X] T013 [P] Add SQLAlchemy ORM models `Source` and `ChapterSource` to `packages/documentlm_core/src/documentlm_core/db/models.py`
- [X] T014 [P] Add SQLAlchemy ORM models `AtomicChapter`, `MarginComment`, and `ChapterChunk` (pgvector column) to `packages/documentlm_core/src/documentlm_core/db/models.py`
- [X] T015 Create Alembic env + initial migration creating all tables and enabling pgvector in `packages/documentlm_core/src/documentlm_core/db/migrations/`
- [X] T016 Create FastAPI app factory with lifespan (DB startup check) and `get_session` dependency in `apps/api/src/api/main.py`
- [X] T017 [P] Create pytest fixtures (`async_session`, `test_client`, `db_rollback`) in `packages/documentlm_core/tests/conftest.py` and `apps/api/tests/conftest.py`
- [X] T018 Write integration test verifying all migrations apply cleanly and pgvector extension exists in `packages/documentlm_core/tests/integration/test_migrations.py`
- [X] T019 Create `Source` CRUD service (create with deduplication, list by topic, verify, reject) in `packages/documentlm_core/src/documentlm_core/services/source.py`
- [X] T020 [P] Write unit tests for `source.py` service (deduplication logic, status transitions) in `packages/documentlm_core/tests/unit/test_source_service.py`

**Checkpoint**: `uv run alembic upgrade head` succeeds; `uv run pytest packages/documentlm_core/tests/` passes.

---

## Phase 3: User Story 1 — Topic Initialisation & Syllabus Generation (Priority: P1) 🎯 MVP

**Goal**: User supplies a topic name → Syllabus Architect generates a prerequisite-aware
syllabus → user views the hierarchical checklist in the UI.

**Independent Test**: `POST /topics` with a topic name → background task completes →
`GET /topics/{id}` returns a syllabus with ≥2 dependency levels and no cycles.

### Tests for User Story 1 ⚠️ Write FIRST, verify they FAIL before implementing

- [X] T021 [P] [US1] Write unit tests for cycle detection and bottleneck identification in `packages/documentlm_core/tests/unit/test_syllabus_service.py` (pure functions, no DB)
- [X] T022 [P] [US1] Write integration tests for topic creation and syllabus retrieval in `packages/documentlm_core/tests/integration/test_topic_service.py`
- [X] T023 [P] [US1] Write integration tests for topic and syllabus routes (POST /topics, GET /topics/{id}, GET /topics/{id}/syllabus) in `apps/api/tests/integration/test_topics_router.py`

### Implementation for User Story 1

- [X] T024 [US1] Implement `Topic` CRUD (create, get, list) in `packages/documentlm_core/src/documentlm_core/services/topic.py`
- [X] T025 [US1] Implement `Syllabus` service — item CRUD, cycle detection (DFS), bottleneck scoring (downstream count), topological sort — in `packages/documentlm_core/src/documentlm_core/services/syllabus.py`
- [X] T026 [US1] Implement Syllabus Architect ADK agent (typed tool functions: `create_syllabus_item`, `add_prerequisite`; all external LLM calls mockable) in `packages/documentlm_core/src/documentlm_core/agents/syllabus_architect.py`
- [X] T027 [P] [US1] Create Jinja2 templates: `apps/api/src/api/templates/base.html`, `topics/list.html`, `topics/detail.html`, `topics/_syllabus_panel.html`, `topics/_syllabus_item.html`
- [X] T028 [US1] Create FastAPI router `apps/api/src/api/routers/topics.py`: `GET /`, `POST /topics`, `GET /topics/{topic_id}`, `GET /topics/{topic_id}/status` (with background task invoking Syllabus Architect)
- [X] T029 [US1] Create FastAPI router `apps/api/src/api/routers/syllabus.py`: `GET /topics/{topic_id}/syllabus` returning HTMX partial
- [X] T030 [US1] Register `topics` and `syllabus` routers in `apps/api/src/api/main.py`; add structured logging for all agent invocations

**Checkpoint**: Full US1 flow works end-to-end. Cycle detection rejects bad prereqs. All US1 tests pass.

---

## Phase 4: User Story 2 — Targeted Chapter Drafting (Priority: P2)

**Goal**: User selects an unblocked syllabus node → Chapter Scribe drafts a chapter using
Core Bucket sources → user reads the chapter with inline citations.

**Independent Test**: With ≥1 VERIFIED source in DB, `POST /syllabus-items/{id}/chapter` on
an unblocked node → background task completes → `GET /chapters/{id}` returns prose with
citations. Attempt on a blocked node returns HTTP 409.

### Tests for User Story 2 ⚠️ Write FIRST, verify they FAIL before implementing

- [X] T031 [P] [US2] Write unit tests for chapter service (blocking check, context folding logic, citation-only-verified guard) in `packages/documentlm_core/tests/unit/test_chapter_service.py`
- [X] T032 [P] [US2] Write integration tests for chapter creation and retrieval in `packages/documentlm_core/tests/integration/test_chapter_service.py`
- [X] T033 [P] [US2] Write integration tests for chapter routes (POST draft, GET chapter, GET status, 409 on blocked) in `apps/api/tests/integration/test_chapters_router.py`

### Implementation for User Story 2

- [X] T034 [US2] Implement `Chapter` service — blocking guard, context folding (summaries of prior chapters), chapter persist, citation linking (VERIFIED sources only) — in `packages/documentlm_core/src/documentlm_core/services/chapter.py`
- [X] T035 [US2] Implement Chapter Scribe ADK agent (typed tools: `draft_chapter`, `fetch_context_summaries`; mocked in tests) in `packages/documentlm_core/src/documentlm_core/agents/chapter_scribe.py`
- [X] T036 [P] [US2] Create templates: `apps/api/src/api/templates/chapters/detail.html`, `chapters/_status_card.html`, `chapters/_citation.html`
- [X] T037 [US2] Add chapter routes to `apps/api/src/api/routers/chapters.py`: `POST /syllabus-items/{item_id}/chapter`, `GET /chapters/{chapter_id}`, `GET /chapters/{chapter_id}/status`; raise 409 if item is blocked
- [X] T038 [US2] Register `chapters` router in `apps/api/src/api/main.py`

**Checkpoint**: US2 flow works end-to-end. Blocked nodes return 409. Citations only from VERIFIED sources. All US2 tests pass.

---

## Phase 5: User Story 3 — Progress Tracking & Pedagogical Blocking (Priority: P3)

**Goal**: User updates a SyllabusItem status (UNRESEARCHED → IN_PROGRESS → MASTERED) via
the UI; downstream nodes become available for drafting once prerequisites are satisfied.

**Independent Test**: `PATCH /syllabus-items/{id}/status` with `status=MASTERED` on a
prerequisite → subsequent `GET /topics/{id}/syllabus` shows its dependent node as unblocked.

### Tests for User Story 3 ⚠️ Write FIRST, verify they FAIL before implementing

- [X] T039 [P] [US3] Write unit tests for status transition and downstream unblocking logic in `packages/documentlm_core/tests/unit/test_status_blocking.py`
- [X] T040 [P] [US3] Write integration tests for status update route in `apps/api/tests/integration/test_syllabus_router.py`

### Implementation for User Story 3

- [X] T041 [US3] Extend `packages/documentlm_core/src/documentlm_core/services/syllabus.py` with `update_status` function that persists the new status and returns a `SyllabusItemRead` with the derived `is_blocked` flag
- [X] T042 [P] [US3] Create template `apps/api/src/api/templates/syllabus/_item_row.html` rendering status badge (unresearched / in-progress / mastered) and blocked overlay
- [X] T043 [US3] Add `PATCH /syllabus-items/{item_id}/status` to `apps/api/src/api/routers/syllabus.py` returning updated `_item_row.html` partial

**Checkpoint**: Changing a prerequisite to MASTERED visually unblocks dependents in the UI without a page reload. All US3 tests pass.

---

## Phase 6: User Story 4 — Active Reading via Margin Comments (Priority: P4)

**Goal**: User highlights a passage in a chapter and adds a comment → Chapter Scribe returns
a targeted inline response anchored to that paragraph → user can resolve the comment.

**Independent Test**: `POST /chapters/{id}/comments` with a `paragraph_anchor` and `content`
→ background task runs → response text appears inline. `PATCH /comments/{id}/resolve` → comment
shows resolved state.

### Tests for User Story 4 ⚠️ Write FIRST, verify they FAIL before implementing

- [X] T044 [P] [US4] Write unit tests for margin comment service (create, resolve, response attachment) in `packages/documentlm_core/tests/unit/test_margin_comment_service.py`
- [X] T045 [P] [US4] Write integration tests for comment routes in `apps/api/tests/integration/test_chapters_router.py`

### Implementation for User Story 4

- [X] T046 [US4] Create `MarginComment` service (create comment, attach agent response, resolve) in `packages/documentlm_core/src/documentlm_core/services/margin_comment.py`
- [X] T047 [US4] Extend `packages/documentlm_core/src/documentlm_core/agents/chapter_scribe.py` with `respond_to_comment` typed tool function (mockable)
- [X] T048 [P] [US4] Create templates: `apps/api/src/api/templates/chapters/_margin_comment.html` (open and resolved states), update `chapters/detail.html` to render per-paragraph comment anchors
- [X] T049 [US4] Add `POST /chapters/{chapter_id}/comments` and `PATCH /comments/{comment_id}/resolve` to `apps/api/src/api/routers/chapters.py`

**Checkpoint**: Margin comment flow works end-to-end. Resolved comments display distinctly. All US4 tests pass.

---

## Phase 7: User Story 5 — Automated Bibliography Aggregation (Priority: P5)

**Goal**: Academic Scout discovers sources into the verification queue → user promotes to Core
Bucket → bibliography view shows deduplicated citations with back-links to citing chapters.

**Independent Test**: Create two chapters each citing the same source → `GET /topics/{id}/bibliography`
lists the source exactly once with links to both chapters. Scout discovery adds new sources to
the queue without duplicates.

### Tests for User Story 5 ⚠️ Write FIRST, verify they FAIL before implementing

- [X] T050 [P] [US5] Write unit tests for bibliography aggregation and deduplication in `packages/documentlm_core/tests/unit/test_bibliography_service.py`
- [X] T051 [P] [US5] Write integration tests for source queue and bibliography routes in `apps/api/tests/integration/test_sources_router.py`

### Implementation for User Story 5

- [X] T052 [US5] Create `Bibliography` service (deduplicated query across all chapters in a VirtualBook, back-link mapping) in `packages/documentlm_core/src/documentlm_core/services/bibliography.py`
- [X] T053 [US5] Implement Academic Scout ADK agent (typed tools: `search_arxiv`, `search_youtube`; all HTTP calls via `httpx` and mockable) in `packages/documentlm_core/src/documentlm_core/agents/academic_scout.py`
- [X] T054 [P] [US5] Create templates: `apps/api/src/api/templates/sources/queue.html`, `sources/_row.html`, `topics/_bibliography.html`
- [X] T055 [US5] Create `apps/api/src/api/routers/sources.py`: `GET /topics/{topic_id}/sources`, `POST /topics/{topic_id}/sources/discover` (background Scout task), `PATCH /sources/{source_id}/verify`, `PATCH /sources/{source_id}/reject`
- [X] T056 [US5] Create `apps/api/src/api/routers/bibliography.py`: `GET /topics/{topic_id}/bibliography` returning lazy-loaded HTMX partial
- [X] T057 [US5] Register `sources` and `bibliography` routers in `apps/api/src/api/main.py`

**Checkpoint**: Full bibliography pipeline works. Source deduplication verified. Scout mocked in tests. All US5 tests pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, CSS, Docker production config, and final quality gates.

- [X] T058 [P] Seed `apps/api/src/api/static/style.css` by copying `/Users/will/projects/document-projects/documentLM/static/style.css` verbatim, then add learning-tracker-specific classes on top: `.syllabus-tree`, `.syllabus-item`, `.status-badge` (unresearched/in-progress/mastered colours), `.blocked-overlay`, `.margin-comment` sidebar, `.chapter-content`; also copy `base.html` from `documentLM/src/writer/templates/base.html` and adapt brand name + nav for learning-tracker
- [X] T059 Add structured JSON logging middleware to `apps/api/src/api/main.py`: log every request (method, path, status, duration) and catch-all exception handler that logs tracebacks before returning 500
- [X] T060 [P] Verify every exception boundary in `packages/documentlm_core/src/documentlm_core/services/` logs with `logger.exception()` — no silent `except: pass` blocks
- [X] T061 [P] Run `uv run ruff check . && uv run ruff format .` across all packages; fix any violations
- [X] T062 [P] Run `uv run mypy packages/ apps/` in strict mode; resolve all errors (no `Any`, no bare `dict`)
- [ ] T063 Run full quickstart.md validation: `docker compose up -d`, `alembic upgrade head`, full `pytest` suite, then manual smoke test per quickstart.md steps

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Requires Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Requires Phase 2
- **Phase 4 (US2)**: Requires Phase 2 (needs Source model from foundational); also benefits from Phase 3 being done (needs SyllabusItem + blocking)
- **Phase 5 (US3)**: Requires Phase 3 (extends syllabus service)
- **Phase 6 (US4)**: Requires Phase 4 (extends chapter routes and Chapter Scribe)
- **Phase 7 (US5)**: Requires Phase 2 (Source model); independent of US3/US4
- **Phase 8 (Polish)**: Requires all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — no other story dependency
- **US2 (P2)**: Foundational + US1 (needs SyllabusItem and blocking check)
- **US3 (P3)**: US1 (extends syllabus service)
- **US4 (P4)**: US2 (extends Chapter Scribe and chapter routes)
- **US5 (P5)**: Foundational only (Source model) — independent of US1–US4

### Within Each User Story

- Tests MUST be written and FAIL before implementation begins (constitution Principle I)
- Pydantic schemas before services
- Services before routes
- Routes before templates (use placeholder template first if needed)
- Story complete and all tests green before moving to next story

### Parallel Opportunities

All tasks marked `[P]` within a phase can run simultaneously. Key batches:

**Phase 1**: T002, T003, T004, T005, T006, T007, T008 — all in parallel
**Phase 2**: T011, T012, T013, T014 — all ORM models in parallel; T019 + T020 in parallel
**Phase 3**: T021, T022, T023 — all test files in parallel; T027 template in parallel with T024–T026
**Phase 4**: T031, T032, T033 — test files; T036 template in parallel with T034–T035

---

## Parallel Example: User Story 1

```bash
# Write all US1 tests together (they touch different files):
Task T021: packages/documentlm_core/tests/unit/test_syllabus_service.py
Task T022: packages/documentlm_core/tests/integration/test_topic_service.py
Task T023: apps/api/tests/integration/test_topics_router.py

# Write templates in parallel with service/agent implementation:
Task T027: apps/api/src/api/templates/topics/*.html
Task T024: services/topic.py
Task T025: services/syllabus.py
Task T026: agents/syllabus_architect.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `uv run pytest`, manual smoke test of topic creation and syllabus view
5. Demo: user can create a topic and see a syllabus — first deliverable

### Incremental Delivery

1. Setup + Foundational → working DB + app skeleton
2. US1 → topic + syllabus generation (MVP demo)
3. US2 → chapter drafting (core value delivery)
4. US3 → status tracking + blocking enforcement
5. US4 → margin comments (active reading)
6. US5 → source discovery + bibliography

### Parallel Team Strategy

With two developers after Phase 2 is complete:
- Developer A: US1 → US2 → US4 (topic/chapter/comments chain)
- Developer B: US3 → US5 (status/blocking + bibliography)

---

## Notes

- `[P]` = different files, no incomplete-task dependencies
- `[USn]` maps task to spec.md user story for traceability
- Tests MUST be written and verified to FAIL before implementation (TDD — constitution P-I)
- Every service function MUST have fully typed signature — no `Any`, no bare `dict` (constitution P-II)
- Every `except` block MUST call `logger.exception()` (constitution P-V)
- `ruff check` + `mypy` MUST pass before marking any task complete (constitution Quality Gates)
- Commit after each task or logical group
- Stop at each phase checkpoint to validate the story independently
