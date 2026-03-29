# Tasks: Source Extraction Pipeline

**Input**: Design documents from `/specs/003-source-extraction-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/pipeline-service-api.md ✅

**Tests**: Included — constitution mandates Test-First; ephemeral ChromaDB client in tests, HTTP extraction mocked.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

## Path Conventions

- Core package: `packages/documentlm-core/src/documentlm_core/`
- Core tests: `packages/documentlm-core/tests/`
- API templates: `apps/api/src/api/templates/`
- Repo root: `./`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies and Docker configuration

- [x] T001 Add `chromadb` and `sentence-transformers` to `packages/documentlm-core/pyproject.toml` and run `uv sync`
- [x] T002 [P] Create `docker-compose.yml` at repo root with postgres-only service (see research.md §8 — no ChromaDB service, embedded client only)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema, enums, and config changes that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Add `SourceType` and `IndexStatus` StrEnums to `packages/documentlm-core/src/documentlm_core/schemas.py`
- [x] T004 [P] Add `source_type`, `index_status`, `index_error`, `content` columns to `Source` model in `packages/documentlm-core/src/documentlm_core/db/models.py`
- [x] T005 Create Alembic migration `packages/documentlm-core/src/documentlm_core/db/migrations/versions/0003_add_source_index_fields.py` with up/down SQL from data-model.md
- [x] T006 [P] Add `chroma_path: str` field to `Settings` in `packages/documentlm-core/src/documentlm_core/config.py` (default `"./chroma_data"`, alias `CHROMA_PATH`)
- [x] T007 Update `SourceRead` in `packages/documentlm-core/src/documentlm_core/schemas.py` to include `source_type`, `index_status`, `index_error`, `content` fields per data-model.md

**Checkpoint**: Foundation ready — run `alembic upgrade head` and confirm migration applies cleanly

---

## Phase 3: US1 + US2 — Pipeline Core + All Source Types (Priority: P1) 🎯 MVP

**Goal**: Every source is extracted, chunked, and indexed into ChromaDB immediately when added or discovered; all source types go through the same pipeline

**Independent Test**: Add a SEARCH source with a URL to a topic → confirm `index_status` transitions to INDEXED; add a second source → confirm it is also indexed; inspect ChromaDB collection to confirm chunks are present for the topic

### Tests for US1/US2 ⚠️ Write these first — ensure they FAIL before implementing

- [x] T008 [P] [US1] Write `packages/documentlm-core/tests/unit/test_chroma_service.py` covering: `get_or_create_collection` creates a collection; `upsert_source_chunks` stores chunks with correct IDs and metadata; `query_topic_chunks` returns ranked chunks; `delete_source_chunks` removes all chunks for a source; `query_topic_chunks` returns empty list when collection does not exist — use `chromadb.EphemeralClient()`
- [x] T009 [P] [US1] Write `packages/documentlm-core/tests/unit/test_pipeline.py` covering: SEARCH-with-URL source triggers `fetch_url_text`, sets `index_status=INDEXED`; PDF_UPLOAD uses stored content, skips fetch; RAW_TEXT uses stored content, skips fetch; URL_SCRAPE calls `fetch_url_text`; YOUTUBE_TRANSCRIPT calls `fetch_youtube_transcript`; SEARCH DOI-only sets `index_status=FAILED` with correct message; extraction failure sets `index_status=FAILED`, populates `index_error`, does not raise; already-INDEXED source returns immediately without re-fetching (US4) — mock all HTTP calls and ChromaDB via `chromadb.EphemeralClient()`

### Implementation for US1/US2

- [x] T010 [US1] Implement `packages/documentlm-core/src/documentlm_core/services/chroma.py` with all 5 functions per contract: `get_chroma_client` (returns `PersistentClient` from `settings.chroma_path`), `get_or_create_collection`, `upsert_source_chunks` (chunk IDs: `{source_id_hex}_{i}`), `query_topic_chunks` (returns empty list on missing collection), `delete_source_chunks`
- [x] T011 [US1] Implement `packages/documentlm-core/src/documentlm_core/services/pipeline.py`: `extract_and_index_source(source_id, session)` — idempotency check at entry (`index_status == INDEXED` → return), full dispatch table for all source types (PDF_UPLOAD/RAW_TEXT: use `source.content`; URL_SCRAPE/SEARCH-with-URL: `await fetch_url_text`; YOUTUBE_TRANSCRIPT: `await fetch_youtube_transcript`; SEARCH DOI-only: mark FAILED), chunk via `nlp_utils.chunk_sentences`, upsert to ChromaDB, set `index_status=INDEXED`, catch all exceptions → set FAILED + log with traceback, flush session (do NOT commit)
- [x] T012 [US2] Add inline pipeline call in `packages/documentlm-core/src/documentlm_core/agents/academic_scout.py`: after each `await create_source(session, ...)` call `await extract_and_index_source(source.id, session)`
- [x] T013 [US1] Add index status badge to `apps/api/src/api/templates/sources/_row.html` alongside existing verification badge: `<span class="status-badge status-index-{{ source.index_status | lower }}">{{ source.index_status }}</span>`

**Checkpoint**: All unit tests T008/T009 pass; SEARCH sources indexed automatically when academic scout runs; badge visible in UI

---

## Phase 4: US3 — Scoped Retrieval in Chapter Scribe (Priority: P2)

**Goal**: When generating a chapter, the agent receives the most relevant portions of the topic's sources — top 10 chunks (~5,000 chars) scoped to the syllabus item's title and description

**Independent Test**: Index a source covering two distinct sub-topics (A and B); generate chapters for syllabus items corresponding to each; confirm chapter A's context contains A-relevant chunks and chapter B's context contains B-relevant chunks

### Tests for US3 ⚠️ Write these first — ensure they FAIL before implementing

- [x] T014 [P] [US3] Write `packages/documentlm-core/tests/integration/test_pipeline_integration.py` covering: index a source with known content → query ChromaDB with item title → confirm relevant chunks returned; chapter scribe prompt contains "Relevant source material:" block when chunks exist; chapter scribe proceeds without source block when collection is empty (graceful degradation); total injected context does not exceed 10 chunks

### Implementation for US3

- [x] T015 [US3] Update `packages/documentlm-core/src/documentlm_core/agents/chapter_scribe.py`: add `item_description: str | None` parameter to `run_chapter_scribe`; before prompt construction, call `get_chroma_client()` then `query_topic_chunks(client, topic_id, f"{item_title} {item_description or ''}".strip(), n_results=10)`; if chunks returned, prepend `"Relevant source material:\n\n" + "\n\n---\n\n".join(chunks)` to prompt; proceed unchanged if no chunks
- [x] T016 [US3] Update all callers of `run_chapter_scribe` in `apps/api/src/api/routers/chapters.py` to pass the new `item_description` argument

**Checkpoint**: T014 integration tests pass; chapter scribe prompt includes source material when ChromaDB has indexed content for the topic

---

## Phase 5: US4 — Idempotency Verification (Priority: P2)

**Goal**: A source already extracted and indexed is never re-extracted on subsequent chapter generation calls; pipeline is safe to call multiple times

**Independent Test**: Call `extract_and_index_source` twice on the same INDEXED source; confirm `fetch_url_text` is called exactly once (or zero times for PDF_UPLOAD/RAW_TEXT)

### Tests for US4 ⚠️ Write these first — ensure they FAIL before implementing

- [x] T017 [US4] Add idempotency test to `packages/documentlm-core/tests/unit/test_pipeline.py`: call pipeline on a source with `index_status=INDEXED`; assert no extraction function is called; assert `index_status` remains INDEXED (already covered in T009 — verify test explicitly asserts call count on mocked fetchers)

### Implementation for US4

The idempotency check is implemented in T011. This phase verifies it through tests and ensures the check is robust.

- [x] T018 [US4] Confirm `extract_and_index_source` in `packages/documentlm-core/src/documentlm_core/services/pipeline.py` returns immediately with no side effects when `source.index_status == IndexStatus.INDEXED` (verify against T011 implementation — add log line: `"Source {source_id} already indexed, skipping extraction"`)

**Checkpoint**: T017 test passes; log confirms skip message on second call for INDEXED source

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and cleanup

- [x] T019 [P] Run `ruff check .` and `mypy` across `packages/documentlm-core/` and fix any violations (no `Any`, no bare `dict` signatures)
- [x] T020 [P] Add CSS rules for `.status-index-pending`, `.status-index-indexed`, `.status-index-failed` badge states if not already present in the app's stylesheet
- [x] T021 Run full test suite (`pytest packages/documentlm-core/tests/`) and confirm all unit and integration tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **Phase 3 (US1/US2)**: Depends on Phase 2 — no dependency on Phase 4/5
- **Phase 4 (US3)**: Depends on Phase 3 (ChromaDB service + pipeline must exist to test scribe integration)
- **Phase 5 (US4)**: Depends on Phase 3 (idempotency is in pipeline.py from T011)
- **Phase 6 (Polish)**: Depends on Phases 3–5

### User Story Dependencies

- **US1/US2 (Phase 3)**: No cross-story dependencies — can start after Foundational
- **US3 (Phase 4)**: Depends on pipeline and chroma service from Phase 3 (needs indexed data to query)
- **US4 (Phase 5)**: Implemented in Phase 3 (T011); Phase 5 adds explicit test coverage

### Parallel Opportunities Within Phase 3

- T008 and T009 (test files) — parallel, different files
- T010 (chroma.py) and T012 (academic_scout.py) — parallel after T008/T009 exist
- T011 (pipeline.py) — depends on T010 (chroma.py) for upsert call

---

## Parallel Example: Phase 3

```bash
# Launch test stubs together first (TDD):
Task: "Write tests/unit/test_chroma_service.py (T008)"
Task: "Write tests/unit/test_pipeline.py (T009)"

# Then implement in parallel where possible:
Task: "Implement services/chroma.py (T010)"            # no other impl dependency
Task: "Add index_status badge to _row.html (T013)"     # UI only, no impl dependency
# After T010 completes:
Task: "Implement services/pipeline.py (T011)"
Task: "Add pipeline call in academic_scout.py (T012)"
```

---

## Implementation Strategy

### MVP (Phase 1 + Phase 2 + Phase 3 only)

1. Complete Phase 1: Add chromadb dependency + docker-compose.yml
2. Complete Phase 2: DB model + enums + migration + config
3. Complete Phase 3: chroma.py + pipeline.py + scout integration + badge
4. **STOP and VALIDATE**: SEARCH sources discovered by scout are indexed; badge shows INDEXED in UI
5. Chapter scribe can be tested manually (no context injection yet — that's Phase 4)

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready (schema migrated, dependency installed)
2. Phase 3 → All source types extract + index; badge visible (MVP)
3. Phase 4 → Chapter content grounded in source material (core value proposition)
4. Phase 5 → Idempotency verified (performance guarantee)
5. Phase 6 → Quality gates passed

---

## Notes

- All ChromaDB usage in tests MUST use `chromadb.EphemeralClient()` — no filesystem state
- `extract_and_index_source` flushes but does NOT commit; caller is responsible for session commit
- Do NOT call `extract_and_index_source` with uncommitted changes to the same source row
- `fetch_url_text` and `fetch_youtube_transcript` are provided by `nlp_utils` (added in Feature 002); if 002 is not yet deployed, pipeline marks URL_SCRAPE and YOUTUBE_TRANSCRIPT sources as FAILED with "extraction not yet available"
- [P] tasks = different files, no dependencies on incomplete tasks
- Commit after each phase checkpoint at minimum
