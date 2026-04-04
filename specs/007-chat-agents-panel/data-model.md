# Data Model: Chat Agents Panel

**Feature**: 007-chat-agents-panel  
**Phase**: 1 — Design  
**Date**: 2026-04-04

---

## Existing Models (no change)

| Model | Table | Relevant fields |
|-------|-------|-----------------|
| `AtomicChapter` | `atomic_chapters` | `id`, `topic_id`, `syllabus_item_id`, `content` |
| `SyllabusItem` | `syllabus_items` | `id`, `topic_id`, `title`, `description` |
| `Topic` | `topics` | `id`, `user_id`, `title` |
| `UserSourceRef` | `user_source_refs` | `topic_id`, `source_id` |

---

## DB Changes: Migration 0011

**Add four nullable columns to `atomic_chapters`:**

| Column | SQLAlchemy type | Nullable | Default | Notes |
|--------|----------------|----------|---------|-------|
| `quiz_questions` | `JSON` | `True` | `None` | List of `QuizQuestion` dicts; set once on generation |
| `quiz_user_responses` | `JSON` | `True` | `None` | List of `int \| None`; updated on each answer |
| `quiz_passed` | `Boolean` | `True` | `None` | `None` = not attempted; updated after full submission |
| `quiz_generated_at` | `DateTime(timezone=True)` | `True` | `None` | Timestamp of generation |

---

## Pydantic Schemas (new)

### QuizQuestion

```python
class QuizQuestion(BaseModel):
    text: str
    options: list[str]          # exactly 3–4 items
    correct_index: int          # 0-based index into options
    explanation: str            # shown after answer selection
```

### QuizState

```python
class QuizState(BaseModel):
    questions: list[QuizQuestion]
    user_responses: list[int | None]   # parallel to questions; None = unanswered
    passed: bool | None                # None = not completed
    generated_at: datetime
```

### ChatMessage (client-side shape, not persisted)

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
```

### ChatRequest

```python
class ChatRequest(BaseModel):
    messages: list[ChatMessage]   # full history including new user message
    chapter_id: uuid.UUID | None  # if chat is on a chapter detail view
```

### QuizResponseSubmit

```python
class QuizResponseSubmit(BaseModel):
    question_index: int
    selected_option_index: int
```

### QuizAnswerResult

```python
class QuizAnswerResult(BaseModel):
    question_index: int
    is_correct: bool
    explanation: str
    quiz_passed: bool | None   # set when all questions answered
```

---

## State Transitions

### Chapter Quiz State Machine

```
                     ┌────────────────┐
                     │  No quiz data  │ (quiz_questions = NULL)
                     └───────┬────────┘
                             │ GET /chapters/{id}/quiz (first time)
                             ▼
                     ┌────────────────┐
                     │  Generated     │ (quiz_questions set,
                     │  unanswered    │  user_responses = [null, null, ...],
                     └───────┬────────┘  quiz_passed = null)
                             │ POST .../quiz/responses (per question)
                             ▼
                     ┌────────────────┐
                     │  In progress   │ (some responses non-null)
                     └───────┬────────┘
                             │ final answer submitted
                             ▼
              ┌──────────────┴──────────────┐
              │                             │
       score ≥ 70%                    score < 70%
              │                             │
              ▼                             ▼
       ┌─────────┐                   ┌──────────┐
       │  Passed │                   │  Failed  │
       │ passed=T│                   │ passed=F │
       └────┬────┘                   └────┬─────┘
            │                             │
            └──────────── re-take ────────┘
                    (responses reset to null,
                     questions unchanged,
                     passed reset to null)
```

---

## Source Code Layout (new files)

```text
packages/documentlm-core/
└── src/documentlm_core/
    ├── agents/
    │   └── chat_agent.py           # ChatAgent: intent classification + routing
    ├── services/
    │   └── quiz.py                 # get_or_create_quiz, submit_response, reset_quiz
    ├── db/
    │   └── migrations/versions/
    │       └── 0011_add_quiz_columns_to_atomic_chapters.py
    └── schemas.py                  # + QuizQuestion, QuizState, ChatMessage,
                                    #   ChatRequest, QuizResponseSubmit, QuizAnswerResult

apps/api/
└── src/api/
    ├── routers/
    │   └── chat.py                 # /topics/{id}/chat/stream, /chapters/{id}/quiz, ...
    └── templates/
        └── chat/
            ├── _pane.html          # Chat pane shell (toggle button, input, message list)
            ├── _message.html       # Single chat message bubble
            ├── _quiz.html          # Full quiz UI (all questions)
            ├── _quiz_question.html # Single question with answer options
            └── _quiz_result.html   # Pass/fail summary banner

tests/
├── packages/documentlm-core/tests/
│   ├── unit/
│   │   ├── test_quiz_service.py    # Pure logic: score calculation, state transitions
│   │   └── test_chat_agent.py      # Intent classification (mocked LLM)
│   └── integration/
│       └── test_quiz_integration.py  # DB: create/retrieve/update quiz via real Postgres
└── apps/api/tests/
    └── integration/
        └── test_chat_router.py     # HTTP: quiz endpoints via test client
```

---

## PASSING_THRESHOLD

```python
QUIZ_PASSING_THRESHOLD: float = 0.70  # 70% correct to pass
```

Defined as a module-level constant in `documentlm_core/services/quiz.py`.
