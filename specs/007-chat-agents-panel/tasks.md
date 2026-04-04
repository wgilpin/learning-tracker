# Tasks: Chat Agents Panel

**Input**: Design documents from `/specs/007-chat-agents-panel/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/http-endpoints.md ✅, quickstart.md ✅

**TDD**: Tests are written first and must fail before implementation begins (Constitution Principle I).

**Organization**: Tasks grouped by user story — each phase is independently deliverable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- **[Story]**: User story this task belongs to (US1–US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding new files and registering the chat router. No logic yet.

- [X] T001 Create `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py` as an empty module with module docstring
- [X] T002 [P] Create `packages/documentlm-core/src/documentlm_core/services/quiz.py` as an empty module with module docstring
- [X] T003 [P] Create `apps/api/src/api/routers/chat.py` with an empty `APIRouter` and register it in `apps/api/src/api/main.py`
- [X] T004 [P] Create template directory `apps/api/src/api/templates/chat/` with empty placeholder files: `_pane.html`, `_message.html`, `_quiz.html`, `_quiz_question.html`, `_quiz_result.html`
- [X] T005 [P] Create test files: `packages/documentlm-core/tests/unit/test_quiz_service.py`, `packages/documentlm-core/tests/unit/test_chat_agent.py`, `packages/documentlm-core/tests/integration/test_quiz_integration.py`, `apps/api/tests/integration/test_chat_router.py` — each with a single `pass` to confirm import

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data layer and shared schemas that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Add `QuizQuestion`, `QuizState`, `ChatMessage`, `ChatRequest`, `QuizResponseSubmit`, `QuizAnswerResult` Pydantic models to `packages/documentlm-core/src/documentlm_core/schemas.py` — exact field shapes from `data-model.md`
- [X] T007 Add four nullable mapped columns to `AtomicChapter` in `packages/documentlm-core/src/documentlm_core/db/models.py`: `quiz_questions: Mapped[list | None]`, `quiz_user_responses: Mapped[list | None]`, `quiz_passed: Mapped[bool | None]`, `quiz_generated_at: Mapped[datetime | None]` — all with `nullable=True` and `JSON`/`DateTime` column types
- [X] T008 Write Alembic migration `packages/documentlm-core/src/documentlm_core/db/migrations/versions/0011_add_quiz_columns_to_atomic_chapters.py` — adds the four columns from T007; run `uv run manage db upgrade` to verify it applies cleanly
- [X] T009 Add `QUIZ_PASSING_THRESHOLD: float = 0.70` constant to `packages/documentlm-core/src/documentlm_core/services/quiz.py`

**Checkpoint**: Migration applied, schemas importable, `AtomicChapter` ORM has four new columns — all user story phases can now begin.

---

## Phase 3: User Story 1 — Ask a Question (Priority: P1) 🎯 MVP

**Goal**: Togglable chat pane on the topic detail page that answers free-text questions by querying ChromaDB for topic material and streaming the response.

**Independent Test**: Open a topic with source material; open the chat pane; type "What is the main idea?"; verify a streaming response appears referencing the material. Confirm suggested buttons ("Give me the quiz", "Set me a question") appear at session start and disappear after first message.

### Tests for User Story 1

> **Write these first — they MUST fail before implementation begins.**

- [X] T010 [P] [US1] Write unit test in `packages/documentlm-core/tests/unit/test_chat_agent.py`: `test_stream_qa_response_calls_chroma` — mock `query_topic_chunks_with_sources` and `_run_agent`; assert that `stream_qa_response` yields at least one non-empty string chunk
- [X] T011 [P] [US1] Write integration test in `apps/api/tests/integration/test_chat_router.py`: `test_chat_stream_qa_returns_sse` — POST to `/topics/{topic_id}/chat/stream` with a simple Q&A message; mock the ADK runner; assert `content-type: text/event-stream` and at least one `data:` line with `"done": false`

### Implementation for User Story 1

- [X] T012 [US1] Implement `stream_qa_response(messages: list[ChatMessage], topic_id: uuid.UUID, session: AsyncSession) -> AsyncIterator[str]` in `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py` — queries ChromaDB via `query_topic_chunks_with_sources`, builds prompt from chunks + conversation history, streams ADK agent response chunks; logs at INFO/DEBUG per constitution
- [X] T013 [US1] Implement `POST /topics/{topic_id}/chat/stream` endpoint in `apps/api/src/api/routers/chat.py` — validates topic ownership; calls `stream_qa_response`; returns `StreamingResponse` with `media_type="text/event-stream"` emitting `{"chunk": "...", "done": false}` events and a final `{"chunk": "", "done": true}`; wraps agent call in try/except with `logger.exception`
- [X] T014 [US1] Write `apps/api/src/api/templates/chat/_pane.html` — chat pane shell containing: suggested message buttons div (visible when `data-empty="true"`), scrollable message list div, textarea + submit button form; suggested buttons have `data-message` attributes consumed by JS
- [X] T015 [US1] Write `apps/api/src/api/templates/chat/_message.html` — single message bubble partial: `role` determines CSS class (`chat-message--user` or `chat-message--assistant`); assistant messages render `content` through `markdown_filter` (existing Jinja2 filter pattern)
- [X] T016 [US1] Modify `apps/api/src/api/templates/topics/detail.html` — add `.chat-panel` as third flex child to `.topic-detail-columns`; add toggle button to topic header; include `chat/_pane.html`; add inline JS (~35 lines) for: `messages` array, `fetch` + `ReadableStream` SSE consumer, `appendMessage(role, content)`, suggested button click handler that populates and submits the input, hide suggested buttons after first message

**Checkpoint**: Chat pane opens, Q&A works end-to-end with streaming, suggested buttons visible at session start and hidden after first message.

---

## Phase 4: User Story 2 — Chapter Quiz (Priority: P2)

**Goal**: Persistent multiple-choice quiz per chapter — generated once, stored on the chapter, user responses persisted, chapter marked passed at ≥70% correct.

**Independent Test**: Request quiz for a chapter (GET `/chapters/{id}/quiz`); answer all questions; verify chapter `quiz_passed = True` in DB when score ≥70%; reload page and confirm same questions reappear with previous answers shown.

### Tests for User Story 2

> **Write these first — they MUST fail before implementation begins.**

- [X] T017 [P] [US2] Write unit tests in `packages/documentlm-core/tests/unit/test_quiz_service.py`:
  - `test_score_quiz_all_correct` — returns 1.0
  - `test_score_quiz_all_wrong` — returns 0.0
  - `test_score_quiz_partial` — returns correct fraction
  - `test_score_quiz_with_nulls` — unanswered (null) responses count as wrong
  - `test_score_quiz_empty` — returns 0.0 for empty list
- [X] T018 [P] [US2] Write integration tests in `packages/documentlm-core/tests/integration/test_quiz_integration.py`:
  - `test_get_or_create_quiz_creates_once` — call twice, assert DB row written once (idempotent)
  - `test_submit_response_updates_db` — submit answer, assert `quiz_user_responses` updated
  - `test_quiz_passed_set_on_final_answer` — submit all correct answers, assert `quiz_passed = True`
  - `test_quiz_not_passed_below_threshold` — submit all wrong answers, assert `quiz_passed = False`
  - `test_reset_quiz_clears_responses_keeps_questions` — reset after completion, assert questions unchanged, responses null, passed null
- [X] T019 [P] [US2] Write integration tests in `apps/api/tests/integration/test_chat_router.py`:
  - `test_get_quiz_returns_html` — GET `/chapters/{id}/quiz`; assert 200 and HTML response
  - `test_post_quiz_response_returns_feedback` — POST a response; assert feedback HTML returned
  - `test_get_quiz_result_after_completion` — complete quiz; GET result; assert pass/fail banner present
  - `test_retake_quiz_clears_responses` — POST retake; assert responses cleared in DB

### Implementation for User Story 2

- [X] T020 [US2] Implement `score_quiz(questions: list[QuizQuestion], responses: list[int | None]) -> float` pure function in `packages/documentlm-core/src/documentlm_core/services/quiz.py` — returns fraction of correctly-answered questions; `None` responses count as wrong
- [X] T021 [US2] Implement `generate_quiz_questions(chapter_content: str, n: int = 5) -> list[QuizQuestion]` in `packages/documentlm-core/src/documentlm_core/services/quiz.py` — calls ADK agent with quiz-generation instruction; parses structured JSON response into `list[QuizQuestion]`; raises `RuntimeError` on parse failure (logged with traceback)
- [X] T022 [US2] Implement `get_or_create_quiz(session: AsyncSession, chapter_id: uuid.UUID) -> QuizState` in `packages/documentlm-core/src/documentlm_core/services/quiz.py` — loads chapter; if `quiz_questions` not null, returns existing `QuizState`; otherwise calls `generate_quiz_questions`, persists to DB, returns new state
- [X] T023 [US2] Implement `submit_response(session: AsyncSession, chapter_id: uuid.UUID, question_index: int, selected_index: int) -> QuizAnswerResult` in `packages/documentlm-core/src/documentlm_core/services/quiz.py` — validates index bounds; writes answer to `quiz_user_responses[question_index]`; if all answered, scores and sets `quiz_passed`; returns `QuizAnswerResult` with correctness, explanation, and `quiz_passed` if final answer
- [X] T024 [US2] Implement `reset_quiz(session: AsyncSession, chapter_id: uuid.UUID) -> None` in `packages/documentlm-core/src/documentlm_core/services/quiz.py` — sets `quiz_user_responses` to `[None] * len(questions)`, `quiz_passed` to `None`; questions unchanged
- [X] T025 [US2] Add quiz intent to `classify_intent` in `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py` — update classification prompt to recognise quiz intent; ensure existing QA intent still classified correctly
- [X] T026 [US2] Add quiz redirect logic to `POST /topics/{topic_id}/chat/stream` in `apps/api/src/api/routers/chat.py` — if `classify_intent` returns `"quiz"` and `chapter_id` is present in request, emit single SSE event `{"quiz_redirect": "/chapters/{chapter_id}/quiz", "done": true}` instead of streaming
- [X] T027 [US2] Implement `GET /chapters/{chapter_id}/quiz` in `apps/api/src/api/routers/chat.py` — calls `get_or_create_quiz`; returns `chat/_quiz.html` with quiz state; validates chapter ownership
- [X] T028 [US2] Implement `POST /chapters/{chapter_id}/quiz/responses` in `apps/api/src/api/routers/chat.py` (form params: `question_index`, `selected_option_index`) — calls `submit_response`; returns `chat/_quiz_question.html`; if `quiz_passed` is not None (final answer), adds `HX-Trigger: quizComplete` response header
- [X] T029 [US2] Implement `GET /chapters/{chapter_id}/quiz/result` and `POST /chapters/{chapter_id}/quiz/retake` in `apps/api/src/api/routers/chat.py`
- [X] T030 [US2] Write `apps/api/src/api/templates/chat/_quiz.html` — loops over questions rendering `_quiz_question.html` for each; includes slot for result banner (populated via `HX-Trigger: quizComplete` swap)
- [X] T031 [US2] Write `apps/api/src/api/templates/chat/_quiz_question.html` — question text; 3–4 option buttons each with `hx-post` to `/quiz/responses`; feedback area hidden until answered; shows prior answer state (correct/incorrect) when `user_response` is not null
- [X] T032 [US2] Write `apps/api/src/api/templates/chat/_quiz_result.html` — pass/fail banner showing score fraction; "Retake" button with `hx-post` to `/retake` targeting the quiz container
- [X] T033 [US2] Add quiz redirect handler to inline JS in `apps/api/src/api/templates/topics/detail.html` — when SSE emits `quiz_redirect`, replace chat message list with HTMX `hx-get` load of quiz URL into the chat pane content area

**Checkpoint**: Full quiz flow works end-to-end — generate, answer, pass state persisted, retake with same questions, prior answers shown on revisit.

---

## Phase 5: User Story 3 — Socratic Questioning (Priority: P3)

**Goal**: Ephemeral Socratic dialogue — one question at a time, generated from user's prior answer, no direct corrections, concludes on demonstrated understanding. No persistence.

**Independent Test**: Send "Set me a question" to the chat; verify one open-ended question is returned. Reply with a vague answer; verify the follow-up questions the gap rather than correcting. Reply with a clear correct answer; verify the agent advances to a harder question. Nothing is written to the DB.

### Tests for User Story 3

> **Write these first — they MUST fail before implementation begins.**

- [X] T034 [P] [US3] Write unit tests in `packages/documentlm-core/tests/unit/test_chat_agent.py`:
  - `test_classify_intent_socratic` — assert phrases like "lead me through a question", "set me a question", "question my understanding" classify as `"socratic"`
  - `test_stream_socratic_response_yields_single_question` — mock ADK runner; assert response does not contain `?` more than once (single question constraint)

### Implementation for User Story 3

- [X] T035 [US3] Add socratic intent patterns to `classify_intent` in `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py`
- [X] T036 [US3] Implement `stream_socratic_response(messages: list[ChatMessage], topic_id: uuid.UUID, session: AsyncSession) -> AsyncIterator[str]` in `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py` — Socratic system instruction (one question at a time, never correct directly, follow the answer not a script, conclude on demonstrated understanding); full conversation history passed in prompt; queries ChromaDB for topic context; logs ADK inputs/outputs at DEBUG per constitution
- [X] T037 [US3] Update `POST /topics/{topic_id}/chat/stream` routing in `apps/api/src/api/routers/chat.py` to route `"socratic"` intent to `stream_socratic_response`

**Checkpoint**: "Set me a question" triggers Socratic agent; follow-up questions respond to user's prior answer content; no DB writes occur.

---

## Phase 6: User Story 4 — Expand a Content Area (Priority: P4)

**Goal**: Enriched explanations for concepts the learner asks to explore more deeply. Ephemeral, no persistence.

**Independent Test**: Send "Tell me more about gradient descent" in the chat; verify response goes deeper than the chapter already contains, referencing source material. Nothing written to DB.

### Tests for User Story 4

> **Write these first — they MUST fail before implementation begins.**

- [X] T038 [P] [US4] Write unit tests in `packages/documentlm-core/tests/unit/test_chat_agent.py`:
  - `test_classify_intent_expand` — assert phrases like "tell me more about X", "expand on chapter 3", "go deeper on" classify as `"expand"`
  - `test_stream_expand_response_queries_chroma` — mock ChromaDB; assert `query_topic_chunks_with_sources` called with concept text from user message

### Implementation for User Story 4

- [X] T039 [US4] Add expand intent patterns to `classify_intent` in `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py`
- [X] T040 [US4] Implement `stream_expand_response(messages: list[ChatMessage], topic_id: uuid.UUID, session: AsyncSession) -> AsyncIterator[str]` in `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py` — Content Expansion system instruction; extracts concept from final user message; queries ChromaDB; streams enriched explanation; gracefully communicates when material doesn't cover the area
- [X] T041 [US4] Update `POST /topics/{topic_id}/chat/stream` routing in `apps/api/src/api/routers/chat.py` to route `"expand"` intent to `stream_expand_response`

**Checkpoint**: All four intents routed correctly; no intent defaults to Q&A when it shouldn't.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Finishing touches that span all user stories.

- [X] T042 [P] Add graceful no-material handling to all three streaming agents in `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py` — when ChromaDB returns zero chunks, respond with a message directing user to add sources rather than fabricating content
- [X] T043 [P] Add loading indicator to `apps/api/src/api/templates/chat/_pane.html` — show spinner in message list while fetch is in progress; hide on first chunk received
- [X] T044 [P] Add timeout handling to inline JS in `apps/api/src/api/templates/topics/detail.html` — if no SSE event received within 15s, append error message and enable retry
- [X] T045 [P] Add `quiz_passed` visual indicator to chapter syllabus items — update `apps/api/src/api/templates/syllabus/_child_item.html` to show a pass badge when `chapter.quiz_passed is True`; requires loading quiz state in the syllabus query
- [X] T046 Run `uv run ruff check .` and `uv run mypy packages/documentlm-core apps/api` — fix all errors; confirm zero `Any` and zero bare `dict` in new code
- [X] T047 Run full test suite `uv run pytest` — all tests pass, none skipped without recorded reason
- [ ] T048 Verify quickstart.md steps in `specs/007-chat-agents-panel/quickstart.md` — run migration, start app, exercise all four intents manually, confirm quiz pass state persists across page reload

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; all T001–T005 parallel
- **Phase 2 (Foundational)**: Depends on Phase 1 — blocks all user story phases; T006→T007→T008 sequential (schemas before ORM before migration)
- **Phase 3 (US1)**: Depends on Phase 2 — no dependency on US2/US3/US4
- **Phase 4 (US2)**: Depends on Phase 2 + T012 (`stream_qa_response` pattern) + T013 (stream endpoint to extend)
- **Phase 5 (US3)**: Depends on Phase 2 + T013 (stream endpoint routing to extend)
- **Phase 6 (US4)**: Depends on Phase 2 + T013 (stream endpoint routing to extend); can run in parallel with US3
- **Phase 7 (Polish)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Phase 2
- **US2 (P2)**: Can start after Phase 2; extends US1's stream endpoint (T013 must exist) but does not require US1 to be fully complete — T013 stub is sufficient
- **US3 (P3)**: Same as US2 — extends T013 stream endpoint only
- **US4 (P4)**: Same as US3; can run in parallel with US3

### Within Each User Story

1. Tests written first (must fail)
2. Service/agent logic before HTTP endpoints
3. Endpoints before templates
4. Templates before JS integration

### Parallel Opportunities

- T001–T005 (Phase 1): all parallel
- T010–T011 (US1 tests): parallel
- T017–T019 (US2 tests): all parallel
- T034, T038 (US3/US4 tests): parallel
- T042–T045 (Polish): all parallel
- US3 and US4 phases can be worked entirely in parallel

---

## Parallel Example: User Story 2 (Quiz)

```
# Write tests in parallel:
T017: test_quiz_service.py unit tests
T018: test_quiz_integration.py integration tests
T019: test_chat_router.py quiz HTTP tests

# Once tests fail as expected, implement service functions in order:
T020 → T021 → T022 → T023 → T024  (sequential: each builds on prior)

# Then HTTP layer (T025–T029) and templates (T030–T033) in parallel where possible:
T025 [intent] parallel with T026 [routing] parallel with T027 [GET quiz]
T030 + T031 + T032 [templates] all parallel
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (migration + schemas)
3. Complete Phase 3: US1 (Q&A streaming + chat pane)
4. **STOP and VALIDATE**: open topic, send questions, confirm streaming works
5. Suggested buttons appear at session start; disappear after first message

### Incremental Delivery

1. Setup + Foundational → data layer ready
2. US1 → chat pane with Q&A streaming (demo-able)
3. US2 → quiz with persistent pass state (most complex; adds DB writes)
4. US3 → Socratic agent (extends US1's streaming infrastructure, no new DB)
5. US4 → Content Expansion (parallel with US3; same pattern)
6. Polish → error states, pass badge, ruff/mypy clean

---

## Notes

- [P] tasks operate on different files with no dependencies on incomplete tasks in the same phase
- TDD is mandatory per constitution: every test task must fail before its implementation task begins
- ADK agents must be mocked in all unit tests; integration tests hit real local Postgres, not live Gemini
- No `Any`, no bare `dict` in signatures — enforced by mypy strict mode
- The stream endpoint (T013) is the single extension point for US2/US3/US4 routing — keep it clean
- Quiz generation is blocking on first GET; no queue, no background task — acceptable for prototype
