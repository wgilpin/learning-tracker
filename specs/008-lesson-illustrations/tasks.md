# Tasks: Lesson Illustrations

**Input**: Design documents from `/specs/008-lesson-illustrations/`  
**Branch**: `008-lesson-illustrations`  
**Additional context**: Ensure support for `adk web` debugging and full logging at all pipeline stages.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

> **TDD is NON-NEGOTIABLE** (Constitution §I). Test tasks appear before their implementation counterparts. Tests MUST fail before implementation is written.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: No new packages or project scaffolding needed — this is an additive feature. Only a config field and a DB migration are new infrastructure.

*(No tasks — existing project structure is sufficient; foundational tasks begin immediately.)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config, ORM model, Pydantic schemas, and DB migration that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 Add `illustration_model: str` field (default `"gemini-3.1-flash-image-preview"`, alias `ILLUSTRATION_MODEL`) to `Settings` in `packages/documentlm-core/src/documentlm_core/config.py`
- [x] T002 Add `ChapterIllustration` SQLAlchemy ORM model (columns: `id UUID PK`, `chapter_id UUID FK→atomic_chapters ON DELETE CASCADE`, `paragraph_index INTEGER`, `image_data LargeBinary`, `image_mime_type VARCHAR(64)`, `image_description Text`, `created_at TIMESTAMPTZ`; unique constraint on `(chapter_id, paragraph_index)`) and add `illustrations: Mapped[list[ChapterIllustration]]` relationship to `AtomicChapter` in `packages/documentlm-core/src/documentlm_core/db/models.py`
- [x] T003 [P] Add `ParagraphAssessment(BaseModel)` (`requires_image: bool`, `image_description: str`) and `IllustrationRead(BaseModel)` (`id: UUID`, `chapter_id: UUID`, `paragraph_index: int`, `image_mime_type: str`, `image_description: str`, `created_at: datetime`) to `packages/documentlm-core/src/documentlm_core/schemas.py`
- [x] T004 Generate Alembic migration creating `chapter_illustrations` table (run `uv run alembic revision --autogenerate -m "add_chapter_illustrations"`) and verify migration file in `packages/documentlm-core/alembic/versions/`

**Checkpoint**: Foundation ready — user story work can now begin.

---

## Phase 3: User Story 1 — Student Views Illustrated Lesson (Priority: P1) 🎯 MVP

**Goal**: Paragraphs that benefit from illustration display a generated image below their text when a student views a chapter.

**Independent Test**: Generate a chapter, wait for the illustration pipeline to complete, reload the chapter page — at least one paragraph should display an `<img>` element immediately below its text.

### Tests for User Story 1 ⚠️ Write FIRST — ensure they FAIL before implementing

- [x] T005 [P] [US1] Write unit tests for `illustration_assessor` covering: valid JSON assessment returned, JSON wrapped in markdown fences (stripped correctly), malformed JSON returns `ParagraphAssessment(requires_image=False, image_description="")`, empty paragraph text handled — mock the ADK `Runner` — in `packages/documentlm-core/tests/unit/test_illustration_assessor.py`
- [x] T006 [P] [US1] Write unit tests for `image_generator` covering: successful response extracts `(bytes, mime_type)` from `inline_data`, response with no image part returns `None`, API exception caught and returns `None` — mock `google.genai.Client` — in `packages/documentlm-core/tests/unit/test_image_generator.py`
- [x] T007 [P] [US1] Write unit tests for `illustration_service.run_illustration_pipeline` covering: paragraph assessed as requiring image → generator called → `ChapterIllustration` persisted; paragraph assessed as not requiring image → generator never called; generator returns `None` → no DB record written — mock `assess_paragraph` and `generate_image` — in `packages/documentlm-core/tests/unit/test_illustration_service.py`
- [x] T008 [P] [US1] Write integration test verifying `ChapterIllustration` round-trips through PostgreSQL: insert a record with fake image bytes, fetch by `(chapter_id, paragraph_index)`, assert `image_data` and `image_mime_type` are preserved — in `packages/documentlm-core/tests/integration/test_illustration_db.py`

### Implementation for User Story 1

- [x] T009 [US1] Implement `assess_paragraph(paragraph_title: str, paragraph_text: str) -> ParagraphAssessment` in `packages/documentlm-core/src/documentlm_core/agents/illustration_assessor.py` using the ADK `Agent`/`Runner`/`InMemorySessionService` pattern from `chapter_scribe.py`; log prompt at `DEBUG`, log result at `DEBUG`, log parse errors at `WARNING`
- [x] T010 [US1] Create `adk web` debugging wrapper: `packages/documentlm-core/adk_agents/illustration_assessor/__init__.py` (empty) and `packages/documentlm-core/adk_agents/illustration_assessor/agent.py` exposing `root_agent = Agent(name="illustration_assessor", model=settings.gemini_model, instruction=_ASSESSMENT_INSTRUCTION)` imported from `illustration_assessor.py`
- [x] T011 [US1] Implement `generate_image(image_description: str, model: str) -> tuple[bytes, str] | None` in `packages/documentlm-core/src/documentlm_core/agents/image_generator.py` using `google.genai.Client.aio.models.generate_content` with `response_modalities=["IMAGE", "TEXT"]`; extract `inline_data.data` and `inline_data.mime_type` from first image part; log prompt at `DEBUG`, log byte count at `DEBUG`, catch and log all exceptions at `ERROR` with traceback, return `None` on failure
- [x] T012 [US1] Implement `run_illustration_pipeline(chapter_id: UUID, content: str, session: AsyncSession) -> None` in `packages/documentlm-core/src/documentlm_core/services/illustration.py`: split `content` by `\n\n`, iterate paragraphs with 1-based index, call `assess_paragraph`, skip if `requires_image=False`, call `generate_image(description, settings.illustration_model)`, persist `ChapterIllustration` on success; log `INFO` at pipeline start/end with chapter ID and counts; log `ERROR` with traceback on any per-paragraph failure and continue to next paragraph
- [x] T013 [US1] Fetch illustrations for a chapter as a `dict[int, IllustrationRead]` in a new `get_illustrations(session, chapter_id) -> dict[int, IllustrationRead]` function in `packages/documentlm-core/src/documentlm_core/services/illustration.py`
- [x] T014 [US1] Chain `run_illustration_pipeline()` call at the end of `_draft_chapter_bg` in `apps/api/src/api/routers/chapters.py` (after `create_chapter` + `session.commit()`), wrapped in `try/except` that logs `ERROR` with traceback so illustration failures never propagate
- [x] T015 [US1] Add `GET /chapters/{chapter_id}/illustrations/{paragraph_index}` endpoint in `apps/api/src/api/routers/chapters.py` returning `Response(content=image_data, media_type=image_mime_type)` or 404; log `INFO` with chapter ID, paragraph index, and byte count
- [x] T016 [US1] Update `apps/api/src/api/templates/chapters/detail.html`: fetch `illustrations` dict in the route handler that renders this template, pass to context, and inside the paragraph loop add `{% if loop.index in illustrations %}<img src="/chapters/{{ chapter.id }}/illustrations/{{ loop.index }}" alt="{{ illustrations[loop.index].image_description }}" class="chapter-illustration">{% endif %}` below the paragraph `md`-rendered block
- [x] T017 [US1] Update `apps/api/src/api/templates/chapters/_inline.html` with the same illustration rendering pattern used in `detail.html`

**Checkpoint**: User Story 1 fully functional — generate a chapter, observe illustrations in both detail and inline views.

---

## Phase 4: User Story 2 — Graceful Degradation (Priority: P2)

**Goal**: Assessment or image-generation failures for any paragraph never prevent lesson rendering; all failures are observable in logs.

**Independent Test**: Patch `generate_image` to raise an exception for one call; request the chapter page — confirm it renders fully with all paragraph text and no error shown to the student.

### Tests for User Story 2 ⚠️ Write FIRST

- [x] T018 [P] [US2] Extend `tests/unit/test_illustration_service.py` with failure-path tests: `assess_paragraph` raises → pipeline continues for remaining paragraphs; `generate_image` raises → no DB write, pipeline continues; all paragraphs fail → function returns without raising; verify `logger.error` called with traceback string for each failure
- [x] T019 [P] [US2] Write unit test for `_draft_chapter_bg` in `tests/unit/test_chapters_router.py` (or equivalent): mock `run_illustration_pipeline` to raise → chapter endpoint still returns the chapter HTML without error

### Implementation for User Story 2

- [x] T020 [US2] Audit `run_illustration_pipeline` in `packages/documentlm-core/src/documentlm_core/services/illustration.py` to ensure every per-paragraph `except` block calls `logger.exception(...)` (includes full traceback) and the outer pipeline catch is similarly guarded — add any missing boundaries identified
- [x] T021 [US2] Audit `_draft_chapter_bg` in `apps/api/src/api/routers/chapters.py` to confirm the `try/except` around `run_illustration_pipeline` calls `logger.exception(...)` with chapter ID context — fix if missing

**Checkpoint**: Lessons render correctly even when the illustration service is broken or unavailable.

---

## Phase 5: User Story 3 — Configurable Image Model (Priority: P3)

**Goal**: Developers change the active image generation model by setting `ILLUSTRATION_MODEL` in `.env`, with no code changes required.

**Independent Test**: Set `ILLUSTRATION_MODEL=some-other-model` in the environment, start the app, generate a chapter — confirm logs show `some-other-model` was used for image generation calls.

### Tests for User Story 3 ⚠️ Write FIRST

- [x] T022 [P] [US3] Write unit test verifying `settings.illustration_model` defaults to `"gemini-3.1-flash-image-preview"` and is overridable via env var; write unit test verifying `generate_image` passes the `model` argument through to the `google.genai` client call (not a hardcoded string) — in `packages/documentlm-core/tests/unit/test_illustration_config.py`

### Implementation for User Story 3

- [x] T023 [US3] Verify `generate_image` in `packages/documentlm-core/src/documentlm_core/agents/image_generator.py` accepts `model: str` as a parameter (not `settings.illustration_model` hardcoded inside) and that `run_illustration_pipeline` in `services/illustration.py` passes `settings.illustration_model` as the argument — fix if not already correct; add `logger.info("Using illustration model: %s", model)` at pipeline start

**Checkpoint**: All three user stories independently functional and tested.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T024 [P] Run `ruff check packages/documentlm-core/src/documentlm_core/agents/illustration_assessor.py packages/documentlm-core/src/documentlm_core/agents/image_generator.py packages/documentlm-core/src/documentlm_core/services/illustration.py` and fix any violations
- [x] T025 [P] Run `mypy packages/documentlm-core/src/documentlm_core/agents/illustration_assessor.py packages/documentlm-core/src/documentlm_core/agents/image_generator.py packages/documentlm-core/src/documentlm_core/services/illustration.py` in strict mode and fix all type errors; grep for `: Any` and `-> Any` in new files and eliminate
- [x] T026 Run full `pytest` suite and fix any regressions (including pre-existing failures per project policy)
- [x] T027 [P] Verify `adk web` works with the new `illustration_assessor` wrapper: confirm `packages/documentlm-core/adk_agents/illustration_assessor/agent.py` is discoverable and `root_agent` is importable without error
- [x] T028 [P] Update `quickstart.md` at `specs/008-lesson-illustrations/quickstart.md` to confirm final file paths and model config instructions are accurate

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **User Story 1 (Phase 3)**: Depends on Foundational (T001–T004) — BLOCKS US1 work
- **User Story 2 (Phase 4)**: Depends on US1 implementation (T009–T017) — error paths require the service to exist
- **User Story 3 (Phase 5)**: Depends on T001 (config) and T011/T012 (generator + pipeline) — can be validated once those are written
- **Polish (Phase 6)**: Depends on all user stories complete

### Within Each Phase

- TDD: Test tasks (T005–T008, T018–T019, T022) MUST be written and confirmed failing before the corresponding implementation tasks are started
- Models before services (T002 before T012)
- Services before endpoints (T012 before T014/T015)
- `adk web` wrapper (T010) can be written in parallel with implementation (T011 onward)

### Parallel Opportunities

```
Phase 2 (all parallel after T001/T002):
  T003 ─────────────────────────── schemas
  T004 ─────────────────────────── migration

Phase 3 tests (all parallel):
  T005 ─── assessor unit tests
  T006 ─── image_generator unit tests
  T007 ─── service unit tests
  T008 ─── integration DB test

Phase 3 implementation (partially parallel):
  T009 ─── assessor impl
  T010 ─── adk web wrapper  ← parallel with T009 once _ASSESSMENT_INSTRUCTION exists
  T011 ─── image_generator  ← parallel with T009
  T012 ─── service          ← needs T009 + T011
  T013 ─── get_illustrations ← parallel with T012
  T014 ─── bg task trigger  ← needs T012
  T015 ─── image endpoint   ← needs T013
  T016 ─── detail.html      ← needs T015 ← parallel with T017
  T017 ─── _inline.html     ← needs T015 ← parallel with T016

Phase 4 tests (parallel):
  T018 ─── service failure tests
  T019 ─── router failure test

Phase 6 (parallel):
  T024 ruff check
  T025 mypy
  T027 adk web smoke test
  T028 quickstart update
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 2: Foundational (T001–T004)
2. Write tests (T005–T008) — confirm they fail
3. Implement (T009–T017)
4. Run `pytest` — confirm tests pass
5. **STOP and VALIDATE**: Generate a chapter, observe illustrations in the browser

### Incremental Delivery

1. Foundation + US1 → illustrated lessons working end-to-end (MVP)
2. Add US2 → confirmed safe failure handling
3. Add US3 → confirmed env-var configuration
4. Polish → ruff, mypy, full test suite green

---

## Notes

- [P] = different files, no blocking dependencies within the phase
- Constitution §I (TDD): test tasks MUST be written first and confirmed failing
- Constitution §V (logging): every `except` block MUST call `logger.exception()` — `except: pass` is forbidden
- Constitution §II (typing): no `Any`, no bare `dict` in signatures — run mypy strict before marking any task done
- `adk web` wrapper (T010) follows the same pattern as `packages/documentlm-core/adk_agents/chapter_scribe/agent.py`
- Image bytes are never included in `IllustrationRead` — they are served exclusively through the `/illustrations/{n}` endpoint
