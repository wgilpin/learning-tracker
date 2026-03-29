# Tasks: Topic Source Upload

**Input**: Design documents from `/specs/002-topic-source-upload/`
**Branch**: `003-source-extraction-pipeline` (building 002 on top of 003)
**Prerequisites**: spec.md, research.md, data-model.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1–US5)

---

## Phase 1: Setup (Dependencies)

**Purpose**: Add new library dependencies required by upload source types.

- [x] T001 Add `youtube-transcript-api` and `yt-dlp` to `packages/nlp_utils/pyproject.toml`
- [x] T002 Run `uv sync` to update lockfile at repo root

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB migration, model/schema changes, and service scaffolding that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Add `SourceType` StrEnum (`PDF_UPLOAD`, `URL_SCRAPE`, `YOUTUBE_TRANSCRIPT`, `RAW_TEXT`, `SEARCH`) to `packages/documentlm-core/src/documentlm_core/models.py`
- [x] T004 Add `source_type`, `is_primary`, `content`, `content_hash` columns to the `Source` SQLAlchemy model in `packages/documentlm-core/src/documentlm_core/db/models.py`
- [x] T005 Create Alembic migration `0004_add_primary_source_fields.py` in `packages/documentlm-core/src/documentlm_core/db/migrations/versions/` — adds `is_primary`, `content_hash` columns and `uq_source_topic_content_hash` constraint
- [x] T006 [P] Add `PrimarySourceCreate` Pydantic schema and update `SourceRead` to include `is_primary` in `packages/documentlm-core/src/documentlm_core/schemas.py`
- [x] T007 [P] Add `compute_content_hash(text: str) -> str` (SHA-256 hex) to `packages/documentlm-core/src/documentlm_core/services/source.py`
- [x] T008 [P] Add `list_sources` optional `primary_only: bool = False` parameter to `packages/documentlm-core/src/documentlm_core/services/source.py`
- [x] T009 `apps/api/src/api/routers/sources.py` already exists and is registered in `apps/api/src/api/main.py`

**Checkpoint**: Migration applied, schema types available, router registered — story implementation can begin.

---

## Phase 3: User Story 1 — Upload PDF Sources (Priority: P1) 🎯 MVP

**Goal**: User can attach a PDF on the source intake page; text is extracted and saved as a primary source with inline feedback.

**Independent Test**: Create a topic, upload a PDF syllabus on `/topics/{id}/sources`, confirm a source card appears with extracted text preview and `is_primary=True` in the DB.

- [x] T010 Add `extract_pdf_text_from_bytes(data: bytes) -> str` to `packages/nlp_utils/src/nlp_utils/fetcher.py` using pypdf; raise `ValueError` if no text extracted; export from `packages/nlp_utils/src/nlp_utils/__init__.py`
- [x] T011 Add `create_primary_source(session, data: PrimarySourceCreate) -> tuple[SourceRead, bool]` to `packages/documentlm-core/src/documentlm_core/services/source.py` — deduplication by `content_hash` for `PDF_UPLOAD`/`RAW_TEXT`, by `url` for URL types; returns `(source, was_duplicate)`
- [x] T012 [US1] Change `POST /topics` redirect target from topic detail to `GET /topics/{id}/sources` in `apps/api/src/api/routers/topics.py`
- [x] T013 [US1] `GET /topics/{id}/sources` route in `apps/api/src/api/routers/sources.py` — renders intake page with current primary sources
- [x] T014 [US1] Create source intake page template `apps/api/src/api/templates/sources/intake.html` — tabbed form (PDF/URL/YouTube/Text tabs), source cards, "Generate" button
- [x] T015 [US1] Implement `POST /topics/{topic_id}/sources/extract` in `apps/api/src/api/routers/sources.py` — handles all source types, returns HTMX source card partial
- [x] T016 [US1] Create source card partial template `apps/api/src/api/templates/sources/_card.html` — shows title, type badge, truncated content preview, remove button with `hx-delete`
- [x] T017 [US1] Implement `DELETE /topics/{topic_id}/sources/{source_id}` in `apps/api/src/api/routers/sources.py` — deletes source, returns 200 with `HX-Trigger`

**Checkpoint**: PDF upload → source card displayed inline → source record in DB with `is_primary=True`.

---

## Phase 4: User Story 2 — URL Scraping (Priority: P1)

**Goal**: User can enter a URL on the source intake page; scraped text is saved as a primary source with inline feedback.

**Independent Test**: Add a URL on `/topics/{id}/sources`, confirm a source card appears with scraped text preview and the source URL stored.

- [x] T018 [US2] Add `fetch_url_text(url: str, timeout: float = 30.0) -> str` to `packages/nlp_utils/src/nlp_utils/fetcher.py` using httpx + `extract_clean_html`; raise `ValueError` if extracted text is empty; export from `__init__.py`
- [x] T019 [US2] URL tab included in source intake page `apps/api/src/api/templates/sources/intake.html`
- [x] T020 [US2] URL branch of `POST /topics/{topic_id}/sources/extract` implemented in `apps/api/src/api/routers/sources.py`

**Checkpoint**: URL submission → text scraped → source card displayed inline.

---

## Phase 5: User Story 5 — Primary Sources Take Precedence (Priority: P1)

**Goal**: When generating a syllabus, primary sources are loaded first and passed to the architect; the academic scout logs primaries and searches only after.

**Independent Test**: Create a topic with a PDF syllabus as primary source, trigger generation, confirm the generated chapter structure matches the syllabus; confirm scout logs show primary sources noted before search.

- [x] T021 [US5] Extend `run_syllabus_architect` in `packages/documentlm-core/src/documentlm_core/agents/syllabus_architect.py` to accept `primary_source_texts: list[str] | None = None`
- [x] T022 [US5] Add primary-sources guard at start of `run_academic_scout` in `packages/documentlm-core/src/documentlm_core/agents/academic_scout.py`
- [x] T023 [US5] Add `POST /topics/{id}/generate` route to `apps/api/src/api/routers/topics.py`
- [x] T024 [US5] "Generate" button in intake.html posts to `/topics/{id}/generate`

**Checkpoint**: Topic with primary sources → generated syllabus mirrors source structure → scout log confirms primaries-first order.

---

## Phase 6: User Story 3 — YouTube Transcript (Priority: P2)

**Goal**: User can enter a YouTube URL; the transcript is extracted and saved as a primary source.

**Independent Test**: Provide a YouTube URL with an available transcript; confirm a source card appears with transcript text and the video URL stored.

- [x] T025 [P] [US3] Create `packages/nlp_utils/src/nlp_utils/youtube.py` with `fetch_youtube_transcript(url_or_id: str) -> tuple[str, str]`
- [x] T026 [US3] Export `fetch_youtube_transcript` from `packages/nlp_utils/src/nlp_utils/__init__.py`
- [x] T027 [US3] YouTube tab included in source intake page `apps/api/src/api/templates/sources/intake.html`
- [x] T028 [US3] YouTube branch of `POST /topics/{topic_id}/sources/extract` implemented in `apps/api/src/api/routers/sources.py`

**Checkpoint**: YouTube URL → transcript extracted → source card displayed with video title and truncated transcript.

---

## Phase 7: User Story 4 — Raw Text Paste (Priority: P2)

**Goal**: User can paste raw text; it is saved directly as a primary source without any fetch step.

**Independent Test**: Paste text on the intake page; confirm a source card appears; submitting the same text twice results in one source and a duplicate notice.

- [x] T029 [US4] Raw text tab included in source intake page `apps/api/src/api/templates/sources/intake.html`
- [x] T030 [US4] Raw text branch of `POST /topics/{topic_id}/sources/extract` implemented in `apps/api/src/api/routers/sources.py`; duplicate notice shown via `_card.html`

**Checkpoint**: Raw text paste → source card displayed; duplicate paste shows notice and no duplicate record created.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: UI hardening, error states, and end-to-end validation.

- [x] T031 [P] Error variant in `apps/api/src/api/templates/sources/_card.html` — shows type badge in red with reason
- [x] T032 [P] Error responses in `POST /topics/{topic_id}/sources/extract` return error card partial (not HTTP 4xx) so HTMX swaps inline
- [x] T033 "Generate" button gated via `disableGenerate()`/`enableGenerate()` JS during in-flight HTMX requests in `intake.html`
- [x] T034 [P] Updated `apps/api/src/api/templates/sources/_row.html` with `source_type` badge and `is_primary` indicator
- [x] T035 Migration 0004 applied against dev DB (`uv run alembic upgrade head` — 0003 → 0004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **blocks all user stories**
- **Phase 3–7 (User Stories)**: All depend on Phase 2; can proceed sequentially or in parallel
- **Phase 8 (Polish)**: Depends on all desired stories being complete

### User Story Dependencies

- **US1 (PDF, Phase 3)**: Foundational complete; establishes intake page and `create_primary_source`
- **US2 (URL, Phase 4)**: US1 complete (reuses intake page and card partial)
- **US5 (Precedence, Phase 5)**: US1 or US2 complete (needs at least one source type to test)
- **US3 (YouTube, Phase 6)**: Foundational complete; independent of US1/US2
- **US4 (Raw text, Phase 7)**: Foundational complete; independent of US1/US2

### Within Each Story

- nlp_utils function → service function → router branch → template update
- Always implement service before router; router before template

---

## Implementation Strategy

### MVP (P1 Stories Only — Phases 1–5)

1. Phase 1: Add deps
2. Phase 2: Migration + model + schemas + service + router skeleton
3. Phase 3: PDF upload end-to-end
4. Phase 4: URL scraping
5. Phase 5: Primary source agent integration + generate route
6. **STOP**: Validate PDF + URL + generation with primary-source precedence

### Full Delivery (Add P2 — Phases 6–8)

6. Phase 6: YouTube
7. Phase 7: Raw text
8. Phase 8: Polish and error states

---

## Summary

| Phase | User Story | Priority | Tasks |
|-------|-----------|----------|-------|
| 1 | Setup | — | T001–T002 |
| 2 | Foundational | — | T003–T009 |
| 3 | US1: PDF Upload | P1 🎯 | T010–T017 |
| 4 | US2: URL Scraping | P1 | T018–T020 |
| 5 | US5: Precedence | P1 | T021–T024 |
| 6 | US3: YouTube | P2 | T025–T028 |
| 7 | US4: Raw Text | P2 | T029–T030 |
| 8 | Polish | — | T031–T035 |

**Total**: 35 tasks | **MVP scope**: T001–T024 (24 tasks, all P1 stories)
