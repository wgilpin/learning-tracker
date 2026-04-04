# Research: Chat Agents Panel

**Feature**: 007-chat-agents-panel  
**Phase**: 0 — Research  
**Date**: 2026-04-04

---

## Decision 1: Response Streaming Mechanism

**Decision**: FastAPI `StreamingResponse` with `media_type="text/event-stream"` (SSE), consumed by the frontend via the Fetch API `ReadableStream` (not `EventSource`).

**Rationale**: `EventSource` is GET-only and cannot carry a message body (the conversation history). `fetch` with `ReadableStream` supports POST bodies, works in all modern browsers, and keeps the JS minimal — the existing `detail.html` pattern of small inline `<script>` blocks is sufficient. HTMX SSE extension was considered but requires a persistent connection model that doesn't fit per-message POST semantics.

**Alternatives considered**:
- HTMX SSE extension (`hx-ext="sse"`) — dropped; doesn't work with POST-per-message.
- WebSockets — dropped; too heavy for a prototype, requires separate infrastructure.
- Polling — dropped; produces choppy UX and wastes requests.

---

## Decision 2: Intent Detection and Agent Routing

**Decision**: Single ADK `Agent` per intent class (Q&A/Socratic, Content Expansion), each with its own system instruction. Intent detection uses lightweight LLM classification (one ADK call with a short classification prompt) before routing. Quiz intent bypasses streaming entirely and routes to the quiz service.

**Rationale**: Building one monolithic agent with tool declarations for all intents adds ADK tool-call overhead and complicates streaming (tool call events interleave with text events). Separate agents with pre-routing is simpler, fully typed, and aligns with the existing pattern in `chapter_scribe.py`. Tool-based routing would be the right call at production scale; for a prototype, intent classification + separate handlers is faster to test.

**Alternatives considered**:
- Single ADK agent with `@tool` declarations for quiz/socratic/expand — dropped; tool-call streaming is more complex to implement correctly and the prototype constraint applies.
- Keyword regex intent detection — dropped; too brittle for natural-language phrasing variation; a single lightweight classification call is more robust with minimal overhead.

---

## Decision 3: Quiz Persistence Strategy

**Decision**: Add four nullable columns to `atomic_chapters`: `quiz_questions` (JSON), `quiz_user_responses` (JSON), `quiz_passed` (bool), `quiz_generated_at` (datetime). One migration, no join.

**Rationale**: The quiz belongs to a chapter 1:1 — there will never be multiple quizzes for one chapter. A separate table adds a join with no benefit at this scale. JSON columns for structured question/answer data are already used elsewhere in the schema (`Source.authors`). The four-column approach keeps all quiz state co-located with the chapter record and is readable in a single query.

**Alternatives considered**:
- Separate `chapter_quizzes` table — dropped; one extra table, one extra join, zero benefit for 1:1 relationship at prototype scale.
- Single JSONB column with all quiz state — considered; slightly more compact but harder to query for `quiz_passed` (would need JSONB path extraction). Separate bool column for `quiz_passed` enables a clean DB query for "show chapters the user has passed".

**Quiz question schema** (stored in `quiz_questions`):
```json
[
  {
    "text": "What does backpropagation compute?",
    "options": ["Gradients", "Activations", "Loss values", "Weights"],
    "correct_index": 0,
    "explanation": "Backpropagation computes the gradient of the loss..."
  }
]
```

**User responses schema** (stored in `quiz_user_responses`):
```json
[0, null, 2, 1]
```
Each element is the selected option index (0-based), or `null` if not yet answered.

---

## Decision 4: Chat Session State Location

**Decision**: Client-side only — an in-memory JS array of `{role: "user"|"assistant", content: str}` objects, passed on every POST to `/topics/{topic_id}/chat/stream`. Nothing written to the server for conversational history.

**Rationale**: Spec is explicit: "Chat session state is held entirely in the browser (client-side) for the duration of the page visit; no session data is written to the server." This matches the existing pattern for ephemeral UI state in this codebase.

---

## Decision 5: Chat Pane Layout

**Decision**: Add a third column `chat-panel` to the existing `topic-detail-columns` flex container in `topics/detail.html`. The pane is togglable via a button — hidden by default, sliding in from the right. No new layout framework.

**Rationale**: The existing layout already uses a flex two-column design (`syllabus-nav` + `reading-panel`). Adding a third flex child is the minimal change. CSS `display: none` / `display: flex` toggling is sufficient without animation library.

---

## Decision 6: Socratic Agent Architecture

**Decision**: The Socratic agent is a stateless ADK `Agent` that receives the full conversation history in its prompt on each turn. It has a system instruction encoding the Socratic rules (one question at a time, never correct directly, follow the answer not a script, conclude on demonstrated understanding). The agent does not have a persistent session between turns — history is reconstructed each time from the JS-held message array.

**Rationale**: Google ADK `InMemorySessionService` holds session state in process memory, which is lost across requests. Reconstructing history from the client-passed message array is equivalent and avoids statefulness on the server. This is the same trade-off already implicitly made by the chat session architecture.

---

## Decision 7: Content Expansion Agent

**Decision**: Re-uses the same ADK agent infrastructure as Q&A, differentiated only by system instruction. ChromaDB queries the topic's source chunks for the named concept. Returns plain Markdown streamed as SSE.

**Rationale**: Content Expansion is structurally identical to Q&A (query ChromaDB → build prompt → stream response), with a different instruction emphasis ("go deeper, use examples"). No separate infrastructure needed.

---

## Decision 8: Passing Threshold

**Decision**: A quiz is "passed" when the user answers ≥ 70% of questions correctly. This is hardcoded as a constant in the quiz service (not configurable via DB or settings). As noted in the spec assumptions, this is a planning-phase decision.

**Rationale**: 70% is the most common passing threshold in academic assessment contexts. Making it a Python constant (rather than a settings value) satisfies the YAGNI principle for a prototype.
