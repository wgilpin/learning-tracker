# Implementation Plan: Chat Agents Panel

**Branch**: `007-chat-agents-panel` | **Date**: 2026-04-04 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/007-chat-agents-panel/spec.md`

---

## Summary

Add a toggleable chat pane to the topic detail page, scoped to the current topic's material. Three specialist agents are available — Quiz (persistent, multiple-choice, chapter pass state), Socratic Questioning (ephemeral, one question at a time, Socratic rules), and Content Expansion (ephemeral, richer explanations) — plus a default direct Q&A mode. Intent is detected server-side; the user sees a single chat input. Quiz state (questions, user responses, pass/fail) is persisted to `atomic_chapters` via four new nullable columns. All chat session state except the quiz is held client-side. Responses are streamed as Server-Sent Events via FastAPI `StreamingResponse`.

---

## Technical Context

**Language/Version**: Python 3.12+ managed via `uv` workspaces (monorepo)  
**Primary Dependencies**: FastAPI, HTMX/Jinja2, Google ADK (`google-adk`), SQLAlchemy 2 async, Pydantic v2, ChromaDB  
**Storage**: PostgreSQL 16 (Docker) — `atomic_chapters` table extended with 4 new nullable columns  
**Testing**: pytest + pytest-asyncio (`asyncio_mode=auto`); integration tests against real Docker Postgres  
**Target Platform**: Docker-hosted Linux server, desktop browser  
**Project Type**: Web application (FastAPI backend + HTMX frontend)  
**Performance Goals**: First token delivered to client within 3s of message submit; quiz generation within 10s (blocking, first time only)  
**Constraints**: No JS framework; minimal inline JS consistent with existing `detail.html` pattern; no server-side chat session storage  
**Scale/Scope**: Prototype; single-user sessions; no concurrent chat load testing required

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Question | Status |
|-----------|---------------|--------|
| I. Test-First | Are tests scoped to local infra only (no live LLM/remote API calls)? | ✅ ADK agents mocked in all unit tests; integration tests hit real local Postgres only, not live Gemini |
| II. Strong Typing | Do all new functions have fully annotated signatures? No `Any`, no bare `dict`? | ✅ All new schemas use `BaseModel`; `QuizQuestion`, `QuizState`, `ChatMessage`, `ChatRequest` are typed models |
| III. Simplicity | Is this the simplest implementation satisfying the spec? No unapproved scope? | ✅ Intent detection via one lightweight LLM call; no tool-use infrastructure; quiz stored as JSON columns on existing table |
| IV. Functional Style | Is side-effectful code pushed to the edges? No inheritance for reuse? | ✅ Quiz scoring is a pure function; DB writes isolated to service layer; ADK agents stateless per-call |
| V. Logging | Does every exception boundary log with traceback? No silent failures? | ✅ Chat stream endpoint wraps agent call in try/except with `logger.exception`; quiz generation failure logged before 503 |
| Tech Stack | Python/uv, FastAPI, HTMX, PostgreSQL+Docker, no raw JS framework? | ✅ No JS framework; inline script consistent with existing pattern |
| Quality Gates | ruff + mypy + pytest all pass? No `Any`, no bare `dict` signatures? | ✅ All new code subject to existing ruff/mypy config |

**Post-design re-check**: All principles hold. The streaming fetch pattern requires ~30 lines of inline JS, within acceptable bounds for the "minimal JS" constraint.

---

## Project Structure

### Documentation (this feature)

```text
specs/007-chat-agents-panel/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── http-endpoints.md  ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks command)
```

### Source Code

```text
packages/documentlm-core/
└── src/documentlm_core/
    ├── agents/
    │   └── chat_agent.py          # NEW: intent classification + 3 streaming ADK agents
    ├── services/
    │   └── quiz.py                # NEW: get_or_create_quiz, submit_response, score, reset
    ├── db/
    │   └── migrations/versions/
    │       └── 0011_add_quiz_columns_to_atomic_chapters.py  # NEW: 4 nullable columns
    └── schemas.py                 # MODIFIED: + QuizQuestion, QuizState, ChatMessage,
                                   #   ChatRequest, QuizResponseSubmit, QuizAnswerResult

apps/api/
└── src/api/
    ├── routers/
    │   ├── chat.py                # NEW: SSE stream + quiz CRUD endpoints
    │   └── __init__.py            # MODIFIED: register chat router
    └── templates/
        ├── topics/
        │   └── detail.html        # MODIFIED: add chat pane column + toggle button
        └── chat/
            ├── _pane.html         # NEW: chat pane shell
            ├── _message.html      # NEW: single message bubble
            ├── _quiz.html         # NEW: full quiz UI
            ├── _quiz_question.html # NEW: single question + options
            └── _quiz_result.html  # NEW: pass/fail result banner

tests/
├── packages/documentlm-core/tests/
│   ├── unit/
│   │   ├── test_quiz_service.py   # NEW: score calculation, state transitions (no DB)
│   │   └── test_chat_agent.py     # NEW: intent classification (mocked ADK)
│   └── integration/
│       └── test_quiz_integration.py  # NEW: full quiz lifecycle via real Postgres
└── apps/api/tests/
    └── integration/
        └── test_chat_router.py    # NEW: quiz HTTP endpoints via test client
```

**Structure Decision**: Follows the existing workspace layout. All new backend logic lives in `documentlm-core`; HTTP routing and templates live in `apps/api`. No new packages or apps created.

---

## Implementation Phases

### Phase A: Data Layer

1. **Migration `0011`** — add `quiz_questions`, `quiz_user_responses`, `quiz_passed`, `quiz_generated_at` (all nullable) to `atomic_chapters`.
2. **ORM update** — add four mapped columns to `AtomicChapter` in `models.py`.
3. **Schemas** — add `QuizQuestion`, `QuizState`, `ChatMessage`, `ChatRequest`, `QuizResponseSubmit`, `QuizAnswerResult` to `schemas.py`.
4. **Quiz service** (`services/quiz.py`):
   - `get_or_create_quiz(session, chapter_id) -> QuizState` — retrieves existing quiz or calls LLM to generate; stores result.
   - `submit_response(session, chapter_id, question_index, selected_index) -> QuizAnswerResult` — writes user response, scores, updates `quiz_passed` if all answered.
   - `reset_quiz(session, chapter_id) -> None` — clears `quiz_user_responses` and `quiz_passed`, keeps questions.
   - `score_quiz(questions, responses) -> float` — pure function, returns fraction correct.

**Tests first** (TDD):
- `test_quiz_service.py` (unit): `score_quiz` edge cases (all correct, all wrong, partial, unanswered), `submit_response` state transitions.
- `test_quiz_integration.py` (integration): create chapter → call `get_or_create_quiz` twice (idempotent) → submit all responses → verify `quiz_passed`.

### Phase B: Chat Agent

5. **`chat_agent.py`** in `documentlm_core/agents/`:
   - `classify_intent(message: str) -> Literal["quiz", "socratic", "expand", "qa"]` — single ADK call with classification instruction; mocked in tests.
   - `stream_qa_response(messages, topic_id, session) -> AsyncIterator[str]` — queries ChromaDB for topic chunks, streams answer via ADK agent.
   - `stream_socratic_response(messages, topic_id, session) -> AsyncIterator[str]` — Socratic system instruction; generates one question based on full history.
   - `stream_expand_response(messages, topic_id, session) -> AsyncIterator[str]` — Content Expansion instruction; streams enriched explanation.

   All streaming functions yield text chunks from `runner.run_async()` non-final events plus the final response text.

**Tests first**:
- `test_chat_agent.py` (unit): `classify_intent` returns correct intent for representative phrases; streaming functions are not called in unit tests (ADK mocked at the runner level).

### Phase C: HTTP Layer

6. **`apps/api/routers/chat.py`**:
   - `POST /topics/{topic_id}/chat/stream` — classifies intent; if quiz → returns `{"quiz_redirect": "/chapters/{chapter_id}/quiz"}`; otherwise streams SSE.
   - `GET /chapters/{chapter_id}/quiz` — returns `chat/_quiz.html` (creates quiz if needed).
   - `POST /chapters/{chapter_id}/quiz/responses` — returns `chat/_quiz_question.html`; triggers `HX-Trigger: quizComplete` on last answer.
   - `GET /chapters/{chapter_id}/quiz/result` — returns `chat/_quiz_result.html`.
   - `POST /chapters/{chapter_id}/quiz/retake` — resets responses, returns `chat/_quiz.html`.
7. **Register router** in `apps/api/src/api/routers/__init__.py` (or `main.py`).

**Tests first**:
- `test_chat_router.py` (integration): quiz endpoint round-trip (GET → POST responses → result); auth guard (401 without session); 404 for unknown chapter.

### Phase D: Frontend

8. **`topics/detail.html`** — add `.chat-panel` div as third flex column; add toggle button; include `chat/_pane.html` partial; add inline JS (~30 lines) for: message history array, submit handler using `fetch` + `ReadableStream` for SSE, quiz redirect handling, suggested button click handlers.
9. **`chat/_pane.html`** — suggested message buttons (visible when `messages.length === 0`), message list div, input form.
10. **`chat/_message.html`** — role-styled bubble; Markdown rendering via existing `markdown-it-py` (re-use existing chapter rendering pattern).
11. **`chat/_quiz.html`** — loops over questions, includes `_quiz_question.html` for each; includes result banner slot.
12. **`chat/_quiz_question.html`** — question text, 3–4 option buttons, feedback area (hidden until answered); HTMX `hx-post` on option click.
13. **`chat/_quiz_result.html`** — pass/fail banner with score fraction; "Retake" button (`hx-post` to `/retake`).

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Quiz persistence | JSON columns on `atomic_chapters` | 1:1 relationship; no join; simpler than separate table |
| Streaming transport | `StreamingResponse` + Fetch `ReadableStream` | EventSource is GET-only; no extra infra |
| Intent routing | Lightweight LLM classification call | More robust than regex; simpler than ADK tool-use |
| Quiz generation | Blocking on first GET | Simple; acceptable for prototype; no queue needed |
| Passing threshold | 70% hardcoded constant | YAGNI; academic convention |
| Session state | Client-side JS array | Per spec; consistent with existing ephemeral UI state |
| Socratic history | Reconstructed from client-passed array | ADK InMemorySessionService is per-process and per-request |
