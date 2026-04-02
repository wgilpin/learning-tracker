# Tasks: Syllabus Chapter Management

**Input**: Design documents from `/specs/005-syllabus-chapter-management/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Included — TDD is constitutionally mandated for all backend services and business logic. Test tasks appear before implementation tasks within each user story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Paths reflect the uv workspace layout (`packages/documentlm-core/`, `apps/api/`)

---

## Phase 1: Setup (Shared Schemas)

**Purpose**: Add new Pydantic schemas used across multiple user stories. No DB migrations needed — `syllabus_items` table already has all required columns.

- [X] T00 Add `SyllabusItemUpdate`, `DescriptionGenerateRequest`, and `GeneratedDescriptionRead` Pydantic models to `packages/documentlm-core/src/documentlm_core/schemas.py`

**Checkpoint**: Schemas available — all user story phases can now begin

---

## Phase 2: User Story 1 — Add Chapter with Description (Priority: P1) 🎯 MVP

**Goal**: Users can add a new chapter to a syllabus by providing a title and optional description. Duplicate-title warning is shown but does not block submission.

**Independent Test**: Add a chapter via the syllabus panel → it appears in the list. Submit an empty title → validation error is shown. Submit a title matching an existing chapter → warning banner appears but chapter is saved.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before implementation

- [X] T00 [P] [US1] Write integration test for `POST /topics/{topic_id}/syllabus-items` happy path (title + description) in `apps/api/tests/routers/test_syllabus_crud.py`
- [X] T00 [P] [US1] Write integration test for `POST /topics/{topic_id}/syllabus-items` with empty title returns 422 in `apps/api/tests/routers/test_syllabus_crud.py`
- [X] T00 [P] [US1] Write integration test for `POST /topics/{topic_id}/syllabus-items` with duplicate title returns item row + warning banner in `apps/api/tests/routers/test_syllabus_crud.py`

### Implementation for User Story 1

- [X] T00 [US1] Add `has_duplicate_title(session, topic_id, parent_id, title, exclude_id) -> bool` to `packages/documentlm-core/src/documentlm_core/services/syllabus.py`
- [X] T00 [US1] Implement `POST /topics/{topic_id}/syllabus-items` route in `apps/api/src/api/routers/syllabus.py` (calls `create_syllabus_item`, `has_duplicate_title`; returns `_child_item.html` fragment + optional warning)
- [X] T00 [US1] Create `_add_item_form.html` inline add form template in `apps/api/src/api/templates/syllabus/_add_item_form.html` (title field, description field, submit; no generate button yet — added in US2)
- [X] T00 [US1] Update `apps/api/src/api/templates/topics/_syllabus_panel.html` to include an "Add chapter" button that HTMX-swaps in `_add_item_form.html` below the items list

**Checkpoint**: US1 fully functional — add-with-description works end-to-end

---

## Phase 3: User Story 2 — Add Chapter Without Description (Auto-Flesh Out) (Priority: P2)

**Goal**: Users can click "Generate description" inside the add form to auto-populate the description field using Gemini. The generated text is shown for review/edit before saving.

**Independent Test**: Open the add form, enter a title only, click "Generate description" → description textarea is populated with a relevant AI-generated description. Edit the text → modified version is saved. Simulate Gemini failure → error message appears with retry option.

### Tests for User Story 2 ⚠️ Write FIRST — must FAIL before implementation

- [X] T00 [P] [US2] Write unit test for `generate_item_description` with Gemini mocked (success case, failure case) in `packages/documentlm-core/tests/services/test_syllabus_service.py`
- [X] T0 [P] [US2] Write integration test for `POST /syllabus-items/{item_id}/generate-description` (returns populated textarea fragment, handles Gemini failure with 503) in `apps/api/tests/routers/test_syllabus_crud.py`

### Implementation for User Story 2

- [X] T0 [US2] Implement `generate_item_description(session, topic_id, parent_id, title) -> str` in `packages/documentlm-core/src/documentlm_core/services/syllabus.py` (fetches sibling titles/descriptions for context; direct Gemini call; logs exception + raises `RuntimeError` on failure)
- [X] T0 [US2] Implement `POST /syllabus-items/{item_id}/generate-description` route in `apps/api/src/api/routers/syllabus.py` (returns description textarea fragment on success; error fragment on 503)
- [X] T0 [US2] Update `apps/api/src/api/templates/syllabus/_add_item_form.html` to add "Generate description" button with HTMX targeting the description field, and a `#description-area` swap target for the generated textarea or error fragment

**Checkpoint**: US2 fully functional — generate-description flow works end-to-end

---

## Phase 4: User Story 3 — Edit an Existing Chapter (Priority: P3)

**Goal**: Users can click an edit icon on any syllabus item row to replace it with an inline edit form. Saving updates the item; cancelling restores the original row unchanged.

**Independent Test**: Click edit on an existing item → row becomes a form pre-filled with current values. Update title, save → row shows new title. Cancel → original values unchanged.

### Tests for User Story 3 ⚠️ Write FIRST — must FAIL before implementation

- [X] T0 [P] [US3] Write unit test for `update_syllabus_item` (title update, description update, empty title error, not-found error) in `packages/documentlm-core/tests/services/test_syllabus_service.py`
- [X] T0 [P] [US3] Write integration test for `PATCH /syllabus-items/{item_id}` (happy path, empty title 422, duplicate title warning) in `apps/api/tests/routers/test_syllabus_crud.py`

### Implementation for User Story 3

- [X] T0 [US3] Implement `update_syllabus_item(session, item_id, update) -> SyllabusItemRead` in `packages/documentlm-core/src/documentlm_core/services/syllabus.py`
- [X] T0 [US3] Implement `PATCH /syllabus-items/{item_id}` route in `apps/api/src/api/routers/syllabus.py` (calls `update_syllabus_item`, `has_duplicate_title`; returns updated `_child_item.html` row; swap=outerHTML)
- [X] T0 [US3] Create `_edit_item_form.html` inline edit form template in `apps/api/src/api/templates/syllabus/_edit_item_form.html` (pre-filled title/description; save + cancel buttons; cancel swaps back to read row)
- [X] T0 [US3] Update `apps/api/src/api/templates/syllabus/_child_item.html` to add edit icon button that HTMX-swaps the row with `_edit_item_form.html`

**Checkpoint**: US3 fully functional — inline edit works end-to-end

---

## Phase 5: User Story 4 — Delete a Chapter (Priority: P4)

**Goal**: Users can delete any chapter with a two-step inline confirmation. The confirmation fragment includes a warning when the item has an associated drafted chapter or child items, and a separate warning when it is the last item in the syllabus.

**Independent Test**: Click delete on an item → row swaps to confirmation fragment. Cancel → row restored. Confirm → row removed from DOM. On an item with a drafted chapter → warning is visible in confirmation. On the last remaining item → empty-syllabus warning is visible.

### Tests for User Story 4 ⚠️ Write FIRST — must FAIL before implementation

- [X] T0 [P] [US4] Write unit test for `has_associated_content` and `delete_syllabus_item` (happy path, not-found error, item with chapter, item with children) in `packages/documentlm-core/tests/services/test_syllabus_service.py`
- [X] T0 [P] [US4] Write integration test for `DELETE /syllabus-items/{item_id}` (success removes item, confirmation shows associated-content warning, confirmation shows last-chapter warning) in `apps/api/tests/routers/test_syllabus_crud.py`

### Implementation for User Story 4

- [X] T0 [US4] Implement `has_associated_content(session, item_id) -> bool` and `delete_syllabus_item(session, item_id) -> None` in `packages/documentlm-core/src/documentlm_core/services/syllabus.py`
- [X] T0 [US4] Add `GET /syllabus-items/{item_id}/delete-confirm` route in `apps/api/src/api/routers/syllabus.py` that returns `_delete_confirm.html` with `has_content` and `is_last` context flags
- [X] T0 [US4] Implement `DELETE /syllabus-items/{item_id}` route in `apps/api/src/api/routers/syllabus.py` (calls `delete_syllabus_item`; returns empty 200 with `HX-Reswap: delete`)
- [X] T0 [US4] Create `_delete_confirm.html` confirmation fragment in `apps/api/src/api/templates/syllabus/_delete_confirm.html` (confirm + cancel buttons; conditional associated-content warning; conditional empty-syllabus warning)
- [X] T0 [US4] Update `apps/api/src/api/templates/syllabus/_child_item.html` to add delete icon that triggers `GET /syllabus-items/{item_id}/delete-confirm` (swap=outerHTML on item row) — depends on T019

**Checkpoint**: All four user stories fully functional and independently testable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and final validation across all stories

- [X] T0 [P] Run `ruff check .` and `ruff format .` on `packages/documentlm-core/` and `apps/api/`; fix any issues
- [X] T0 [P] Run `mypy packages/documentlm-core/src --strict`; resolve any type errors in new code (no `Any`, no bare `dict` signatures)
- [X] T0 Run full `pytest` suite; confirm all new and existing tests pass with no skips
- [ ] T030 Manually validate all quickstart.md smoke-test scenarios against the running stack

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on T001 (schemas); T002–T004 tests can start in parallel with T001
- **US2 (Phase 3)**: Depends on Phase 2 complete (needs `_add_item_form.html` from T007)
- **US3 (Phase 4)**: Depends on T001 (schemas); otherwise independent of US1/US2
- **US4 (Phase 5)**: Depends on T019 (edit button in `_child_item.html` for T026); otherwise independent
- **Polish (Phase 6)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Independent after T001
- **US2 (P2)**: Depends on US1's `_add_item_form.html` (T007) — must update that template in T013
- **US3 (P3)**: Independent after T001
- **US4 (P4)**: T026 depends on T019 (same file: `_child_item.html`)

### Within Each User Story

1. Test tasks (T00x) — write and confirm they FAIL
2. Service functions — implement and make tests GREEN
3. Route handler — wire service to HTTP
4. Templates — render HTML fragments
5. Trigger wiring — add buttons/links to existing templates

### Parallel Opportunities

- T002, T003, T004 can run in parallel (same file but additive test functions)
- T009, T010 can run in parallel (different files)
- T014, T015 can run in parallel
- T020, T021 can run in parallel
- T027, T028 can run in parallel (different tools/files)

---

## Parallel Example: User Story 1

```bash
# Write all three tests for US1 in parallel (additive functions in same file):
Task T002: "Integration test: POST /topics/{id}/syllabus-items happy path"
Task T003: "Integration test: POST /topics/{id}/syllabus-items empty title → 422"
Task T004: "Integration test: POST /topics/{id}/syllabus-items duplicate title → warning"

# Then implementation tasks are sequential within US1 (route depends on service; template on route)
```

## Parallel Example: User Story 3 + User Story 4 tests

```bash
# Once US1 complete, US3 and US4 tests can be written in parallel:
Task T014: "Unit test: update_syllabus_item"          # services test file
Task T015: "Integration test: PATCH /syllabus-items"  # routers test file
Task T020: "Unit test: has_associated_content, delete_syllabus_item"
Task T021: "Integration test: DELETE /syllabus-items"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: User Story 1 (T002–T008)
3. **STOP and VALIDATE**: Add-with-description fully works; duplicate warning works
4. Demo/review

### Incremental Delivery

1. Phase 1 → Foundation ready
2. Add US1 → Add-with-description MVP ✓
3. Add US2 → Auto-generate description ✓
4. Add US3 → Edit chapters ✓
5. Add US4 → Delete chapters ✓
6. Each story adds value without breaking previous stories

### Single Developer (Sequential)

Work phases in order: 1 → 2 → 3 → 4 → 5 → 6. Within each phase: tests first (confirm RED), then implement (GREEN), then templates.

---

## Notes

- `[P]` tasks touch different files or are additive functions — safe to parallelize
- `[Story]` label maps to user stories in spec.md
- Constitution requires TDD: every test task must be written and confirmed FAILING before the corresponding implementation task begins
- `_child_item.html` is modified by both US3 (T019) and US4 (T026) — do T019 before T026
- Gemini MUST be mocked in all test contexts (constitution Principle I); use `unittest.mock.patch` or a fixture-level fake
- No DB migrations needed — `syllabus_items` table is unchanged
