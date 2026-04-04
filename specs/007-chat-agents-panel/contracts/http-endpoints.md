# HTTP Endpoint Contracts: Chat Agents Panel

**Feature**: 007-chat-agents-panel  
**Date**: 2026-04-04

All endpoints are authenticated (session cookie required). All request/response bodies are JSON unless noted.

---

## Chat Streaming

### `POST /topics/{topic_id}/chat/stream`

Stream an agent response for the given message history. Returns Server-Sent Events.

**Path params**: `topic_id: UUID`

**Request body**:
```json
{
  "messages": [
    {"role": "user", "content": "What is gradient descent?"},
    {"role": "assistant", "content": "Gradient descent is..."},
    {"role": "user", "content": "Lead me through a question"}
  ],
  "chapter_id": "uuid-or-null"
}
```

**Response**: `Content-Type: text/event-stream`

Each SSE event:
```
data: {"chunk": "Gradient ", "done": false}
data: {"chunk": "descent...", "done": false}
data: {"chunk": "", "done": true}
```

**Error responses**:
- `404` — topic not found or not owned by current user
- `422` — invalid request body

**Notes**:
- The last event always has `"done": true` with an empty `chunk`.
- Intent classification happens server-side. The frontend does not specify the agent; the server infers it from the message content.
- If quiz intent is detected, the server returns a special event: `data: {"quiz_redirect": "/chapters/{chapter_id}/quiz"}` followed by `done: true`. The frontend must handle this by loading the quiz UI.

---

## Quiz

### `GET /chapters/{chapter_id}/quiz`

Retrieve or generate the quiz for a chapter. Returns HTML fragment.

**Path params**: `chapter_id: UUID`

**Response**: `Content-Type: text/html` (HTMX fragment: `chat/_quiz.html`)

- If quiz already exists: returns existing questions with prior user responses pre-populated.
- If no quiz exists: generates questions (blocking, may take ~5–10s), stores them, returns the quiz UI.
- `quiz_passed` state is shown in the response (pass banner, fail summary, or neutral if not yet attempted).

**Error responses**:
- `404` — chapter not found or not owned by current user
- `503` — quiz generation failed (LLM error)

---

### `POST /chapters/{chapter_id}/quiz/responses`

Submit an answer for a single question. Returns HTML fragment for that question's feedback.

**Path params**: `chapter_id: UUID`

**Request body** (form-encoded):
```
question_index=0&selected_option_index=2
```

**Response**: `Content-Type: text/html` (HTMX fragment: `chat/_quiz_question.html`)

- Renders the question with correct/incorrect indicator and explanation.
- If this was the last unanswered question, also includes `HX-Trigger: quizComplete` header so the frontend can load the result banner.

**Error responses**:
- `404` — chapter or quiz not found
- `409` — question already answered (idempotent: returns current state)

---

### `GET /chapters/{chapter_id}/quiz/result`

Returns the pass/fail result banner for a completed quiz.

**Path params**: `chapter_id: UUID`

**Response**: `Content-Type: text/html` (HTMX fragment: `chat/_quiz_result.html`)

- Returns 422 if quiz is not yet complete (not all questions answered).

---

### `POST /chapters/{chapter_id}/quiz/retake`

Reset user responses so the quiz can be retaken. Questions are unchanged.

**Path params**: `chapter_id: UUID`

**Request body**: empty

**Response**: `Content-Type: text/html` (HTMX fragment: `chat/_quiz.html`)

- Returns the quiz UI with all responses cleared and no pass/fail indicator.

---

## Topic Detail Integration

The chat pane is rendered inside the topic detail page. The pane toggle is a button in the topic header; it sets `display` on the `.chat-panel` div. No separate endpoint for the pane shell — it is rendered as part of `topics/detail.html`.
