# Quickstart: Chat Agents Panel

**Feature**: 007-chat-agents-panel  
**Date**: 2026-04-04

---

## Prerequisites

- Docker running (`docker compose up -d`)
- `uv` installed
- `GOOGLE_API_KEY` set in `.env`

---

## Run Migration

```bash
cd apps/api
uv run manage db upgrade
```

This applies migration `0011_add_quiz_columns_to_atomic_chapters` which adds `quiz_questions`, `quiz_user_responses`, `quiz_passed`, and `quiz_generated_at` columns to `atomic_chapters`.

---

## Start the App

```bash
cd /path/to/learning-tracker
docker compose up -d
uv run --project apps/api uvicorn api.main:app --reload
```

Navigate to a topic with at least one chapter generated. The chat pane toggle button appears in the topic header.

---

## Try the Chat Pane

1. Open any topic with source material and a generated chapter.
2. Click the chat toggle button (top right of topic detail).
3. The chat pane opens with two suggested message buttons: **"Give me the quiz"** and **"Set me a question"**.

**To take the quiz:**
- Click "Give me the quiz" (or type it). The quiz loads for the currently-viewed chapter.
- Select an option for each question to receive immediate feedback.
- On completion, a pass/fail banner appears. Pass state is stored on the chapter.

**For Socratic questioning:**
- Click "Set me a question" (or type "lead me through a question").
- Answer the question the agent poses. Follow-up questions are generated from your answer.

**For Q&A / content expansion:**
- Type any question ("What is...") or ask to go deeper ("Tell me more about X").

---

## Run Tests

```bash
# Unit tests (no DB required)
cd /path/to/learning-tracker
uv run pytest packages/documentlm-core/tests/unit/test_quiz_service.py -v
uv run pytest packages/documentlm-core/tests/unit/test_chat_agent.py -v

# Integration tests (Postgres required via Docker)
uv run pytest packages/documentlm-core/tests/integration/test_quiz_integration.py -v
uv run pytest apps/api/tests/integration/test_chat_router.py -v
```

---

## Key Files

| File | Purpose |
|------|---------|
| `packages/documentlm-core/src/documentlm_core/agents/chat_agent.py` | Intent classification + streaming ADK agents |
| `packages/documentlm-core/src/documentlm_core/services/quiz.py` | Quiz generation, answer submission, scoring |
| `packages/documentlm-core/src/documentlm_core/db/migrations/versions/0011_*.py` | DB migration |
| `apps/api/src/api/routers/chat.py` | HTTP endpoints for chat stream + quiz |
| `apps/api/src/api/templates/chat/` | Jinja2 templates for chat pane and quiz UI |
| `apps/api/src/api/templates/topics/detail.html` | Modified to include chat pane column |
