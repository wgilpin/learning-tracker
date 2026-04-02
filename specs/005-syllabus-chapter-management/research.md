# Research: Syllabus Chapter Management

**Branch**: `005-syllabus-chapter-management` | **Date**: 2026-04-01

## Decision Log

### D-001: HTMX Inline Edit Pattern

**Decision**: Inline swap pattern — clicking "Edit" replaces the item row with an edit form in-place; saving swaps the form back to the read row.

**Rationale**: The existing codebase already uses `hx-swap="outerHTML"` and `hx-target` for in-place updates (e.g., status checkbox, margin comment resolution). Inline editing is consistent with this approach, avoids modals (which require JS boilerplate), and keeps the user in the syllabus context. A modal would add complexity for no benefit at prototype scale.

**Alternatives considered**:
- Modal dialog: More JS, harder to test with HTMX, inconsistent with rest of app.
- Navigate to a separate edit page: Breaks flow; user loses their place in the syllabus.

---

### D-002: Description Generation — Direct Gemini vs ADK Agent

**Decision**: Direct Gemini call via `google-generativeai` SDK, not wrapped in an ADK Agent.

**Rationale**: ADK agents are designed for multi-step tool-using tasks (e.g., `SyllabusArchitect` creates multiple items, `ChapterScribe` queries ChromaDB, maps citations). Generating a single short description from a title + context is a one-shot prompt with no tools required. Using ADK for this adds session management overhead with no benefit. The existing `chapter_scribe.py` already imports and configures `google.generativeai` directly for its Gemini client setup — the same pattern applies here.

**Alternatives considered**:
- ADK Agent with no tools: Works but unnecessary indirection for a single completion call.
- Extending `SyllabusArchitect` to handle single-item description: Couples two concerns.

---

### D-003: Duplicate Title Warning Mechanism

**Decision**: Server-side check on form submit — if a duplicate title exists the response includes an HTMX-rendered warning banner above the form (swap into a warning target div), but does not prevent submission. The user can re-submit as-is.

**Rationale**: Client-side duplicate detection (on blur) would require a dedicated HTMX check endpoint on every keystroke or focus-out event, adding complexity. A server-side check on the POST/PATCH is simpler and consistent with how FR-007 (empty title validation) is already positioned. The spec requires a warning, not a hard block.

**Alternatives considered**:
- `hx-trigger="blur"` on title field hitting a `/check-duplicate` endpoint: More responsive but over-engineered for a prototype.
- Client-side JS duplicate check: Violates no-raw-JS constraint.

---

### D-004: Delete Confirmation UI

**Decision**: Inline HTMX confirmation — clicking "Delete" swaps the item row with a confirmation fragment (`_delete_confirm.html`) containing "Yes, delete" and "Cancel" buttons. "Cancel" swaps back to the original row; "Yes, delete" fires the DELETE request and removes the item from the DOM.

**Rationale**: No page navigation needed. Consistent with the existing margin-comment delete pattern. The confirmation fragment can also carry the "last chapter" warning and "has associated content" warning conditionally, rendered server-side.

**Alternatives considered**:
- Browser `confirm()` dialog: No server-side context for warnings; poor UX; not HTMX-native.
- Separate confirmation page: Breaks flow.

---

### D-005: Position of New Chapter in Syllabus

**Decision**: New chapters are appended at the end of the top-level list (or end of a parent's children list) by default. No explicit position input is exposed in this feature.

**Rationale**: The spec explicitly defers reordering to a future feature. Append-at-end is the simplest and most predictable behaviour. The existing `SyllabusItem` model has no explicit `position` or `order` column — ordering currently relies on `created_at` ascending, which append-at-end naturally satisfies.

**Alternatives considered**:
- Insert at position N: Requires reordering all subsequent items; out of scope.
- Prepend: Less natural for a sequential syllabus.

---

### D-006: Scope of Description Generation Context

**Decision**: The generation prompt includes: the topic title, the titles and descriptions of all other top-level sibling items (same `parent_id`), and the new item's title. No ChromaDB/source retrieval.

**Rationale**: For description generation, user intent context (what other chapters exist) is more valuable than source material chunks. ChromaDB retrieval is used by `ChapterScribe` because it's writing full prose chapters from source material — description generation is a much lighter task. Keeping this source-free also means the generation works even when no sources have been indexed.

**Alternatives considered**:
- Include ChromaDB chunks: Adds latency and complexity; source material may not exist yet.
- Include full topic description: Not available in current data model (Topic has only a `title`).
