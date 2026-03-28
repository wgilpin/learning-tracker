# API Route Contracts: Academic Learning Tracker

**Branch**: `001-academic-learning-tracker`
**Date**: 2026-03-28

All routes are served by FastAPI. Routes return HTML partials (for HTMX requests) or full
pages (for direct navigation). JSON responses are used only for status/error payloads where
no HTML rendering is needed.

Convention:
- `HX-Request: true` header → return HTML partial
- No `HX-Request` header → return full page (wraps partial in base layout)
- All mutation routes require `HX-Request: true`

---

## Topics

### `GET /`
**Description**: Landing page. Lists all topics.
**Response**: Full HTML page — list of Topic cards with title and syllabus progress summary.
**HTMX**: Navigable directly; no partial variant needed.

---

### `POST /topics`
**Description**: Create a new topic and trigger syllabus generation via Syllabus Architect.
**Request body** (form): `title: str`, `description: str | None`
**Response**: `HX-Redirect` to `GET /topics/{id}` once the background task is queued.
**Background task**: Runs Syllabus Architect → writes SyllabusItems to DB.
**HTMX**: `hx-post="/topics"`, `hx-target="body"`, swap on redirect.

---

### `GET /topics/{topic_id}`
**Description**: Topic overview page — syllabus tree + VirtualBook table of contents.
**Path params**: `topic_id: UUID`
**Response**: Full HTML page.
**HTMX**: Also returns partial (syllabus + ToC columns) when `HX-Request: true`.

---

### `GET /topics/{topic_id}/status`
**Description**: Syllabus generation progress polling endpoint.
**Path params**: `topic_id: UUID`
**Response**: JSON `{"status": "pending" | "complete" | "error", "item_count": int}`
**HTMX**: Polled via `hx-trigger="every 2s"` until status is `complete` or `error`.

---

## Syllabus Items

### `GET /topics/{topic_id}/syllabus`
**Description**: Syllabus tree partial — all SyllabusItems with status badges and block state.
**Path params**: `topic_id: UUID`
**Response**: HTML partial — ordered list of SyllabusItem rows.
**HTMX**: `hx-get`, `hx-target="#syllabus-panel"`.

---

### `PATCH /syllabus-items/{item_id}/status`
**Description**: Update the status of a SyllabusItem.
**Path params**: `item_id: UUID`
**Request body** (form): `status: "UNRESEARCHED" | "IN_PROGRESS" | "MASTERED"`
**Response**: HTML partial — updated SyllabusItem row (re-renders status badge + downstream
  blocked/unblocked states).
**HTMX**: `hx-patch`, `hx-target="closest .syllabus-item"`, `hx-swap="outerHTML"`.

---

### `POST /syllabus-items/{item_id}/chapter`
**Description**: Request a chapter draft for an unblocked SyllabusItem. Starts a background
  task running the Chapter Scribe agent.
**Path params**: `item_id: UUID`
**Pre-condition**: Item MUST NOT be blocked (no `UNRESEARCHED` direct prerequisites).
  Returns `HTTP 409` if blocked.
**Response**: HTML partial — chapter draft status card with polling target.
**HTMX**: `hx-post`, `hx-target="#chapter-panel"`.

---

## Chapters

### `GET /chapters/{chapter_id}`
**Description**: Full chapter view with content, margin comments, and local citations.
**Path params**: `chapter_id: UUID`
**Response**: Full HTML page (or partial if `HX-Request`).

---

### `GET /chapters/{chapter_id}/status`
**Description**: Chapter draft progress polling.
**Path params**: `chapter_id: UUID`
**Response**: JSON `{"status": "pending" | "complete" | "error"}`
**HTMX**: Polled via `hx-trigger="every 2s"` until done.

---

### `POST /chapters/{chapter_id}/comments`
**Description**: Add a margin comment to a chapter paragraph.
**Path params**: `chapter_id: UUID`
**Request body** (form): `paragraph_anchor: str`, `content: str`
**Response**: HTML partial — the new MarginComment card (open state) with a pending response
  indicator. A background task runs the Chapter Scribe to produce an inline response.
**HTMX**: `hx-post`, `hx-target="#comments-{paragraph_anchor}"`, `hx-swap="afterbegin"`.

---

### `PATCH /comments/{comment_id}/resolve`
**Description**: Mark a margin comment as resolved.
**Path params**: `comment_id: UUID`
**Response**: HTML partial — updated comment card (resolved/greyed state).
**HTMX**: `hx-patch`, `hx-target="closest .margin-comment"`, `hx-swap="outerHTML"`.

---

## Sources

### `GET /topics/{topic_id}/sources`
**Description**: Source verification queue for a topic — shows `QUEUED`, `VERIFIED`, and
  `REJECTED` sources.
**Path params**: `topic_id: UUID`
**Response**: HTML partial (or full page).

---

### `POST /topics/{topic_id}/sources/discover`
**Description**: Trigger the Academic Scout agent to find new sources for the topic.
**Path params**: `topic_id: UUID`
**Response**: HTML partial — pending state card with polling target.
**HTMX**: `hx-post`, `hx-target="#source-queue"`.

---

### `PATCH /sources/{source_id}/verify`
**Description**: Promote a source to the Core Bucket (`VERIFIED`).
**Path params**: `source_id: UUID`
**Response**: HTML partial — updated source row (verified badge).
**HTMX**: `hx-patch`, `hx-target="closest .source-row"`, `hx-swap="outerHTML"`.

---

### `PATCH /sources/{source_id}/reject`
**Description**: Reject a source.
**Path params**: `source_id: UUID`
**Response**: HTML partial — updated source row (rejected/struck-through badge).
**HTMX**: `hx-patch`, `hx-target="closest .source-row"`, `hx-swap="outerHTML"`.

---

## Bibliography

### `GET /topics/{topic_id}/bibliography`
**Description**: Deduplicated master bibliography for the Virtual Book.
**Path params**: `topic_id: UUID`
**Response**: HTML partial — sorted list of verified sources with back-links to citing chapters.
**HTMX**: `hx-get`, `hx-trigger="revealed"` (lazy-loaded when scrolled into view),
  `hx-target="#bibliography-panel"`.

---

## Error Responses

All routes return structured error partials for HTMX requests:

| HTTP Status | Condition |
|-------------|-----------|
| 404 | Resource not found |
| 409 | Chapter draft blocked by unresolved prerequisites |
| 422 | Validation error (malformed form data) |
| 500 | Unexpected server error — always logged with traceback |

Error partials render inline in the relevant panel rather than replacing the whole page.

---

## HTMX Extension Usage

- `hx-ext="sse"` — used on the syllabus generation progress indicator (alternative to polling
  if SSE is preferred; polling is the default for simplicity).
- `hx-boost="true"` — applied to the `<body>` tag for progressive-enhancement page navigation.
- No custom JS event handlers; all interactions via standard HTMX attributes.
