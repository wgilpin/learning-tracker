# Interface Contract: Syllabus Item CRUD Endpoints

**Feature**: 005-syllabus-chapter-management | **Date**: 2026-04-01

All endpoints follow the existing HTMX server-side rendering pattern: responses are HTML fragments swapped into the page by HTMX, not JSON. Errors that should be shown to the user are returned as HTML fragments with appropriate HTTP status codes.

Authentication: all endpoints require an authenticated session (existing middleware). Requests without a valid session return 302 → `/login`.

---

## POST `/topics/{topic_id}/syllabus-items`

**Purpose**: Create a new top-level syllabus item for a topic (or a child item if `parent_id` is provided).

**Request** (form-encoded):
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | string | Yes | Non-empty after strip; max 500 chars |
| `description` | string | No | May be empty |
| `parent_id` | UUID string | No | Must be valid item ID within the same topic |

**Responses**:
| Status | Body | Trigger |
|--------|------|---------|
| 200 OK | HTML fragment: the new `_child_item.html` row | Item created successfully |
| 200 OK (with warning) | HTML fragment: item row + duplicate-title warning banner | Title matches an existing sibling |
| 422 Unprocessable | HTML fragment: form with inline validation error | Title is empty |
| 404 Not Found | HTML fragment: error message | `topic_id` or `parent_id` not found |

**HTMX target**: `hx-swap="beforeend"` into the syllabus items list container; warning banner targets a separate `#syllabus-warning` div.

---

## PATCH `/syllabus-items/{item_id}`

**Purpose**: Update the title and/or description of an existing syllabus item.

**Request** (form-encoded):
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | string | No | If provided: non-empty after strip |
| `description` | string | No | May be empty |

At least one field must be provided.

**Responses**:
| Status | Body | Trigger |
|--------|------|---------|
| 200 OK | HTML fragment: updated `_child_item.html` row (read mode) | Update succeeded |
| 200 OK (with warning) | HTML fragment: item row + duplicate-title warning banner | Title matches an existing sibling |
| 422 Unprocessable | HTML fragment: edit form with inline validation error | Title is empty |
| 404 Not Found | HTML fragment: error message | `item_id` not found |

**HTMX target**: `hx-swap="outerHTML"` on the item row (replaces edit form with read row).

---

## DELETE `/syllabus-items/{item_id}`

**Purpose**: Permanently delete a syllabus item. Cascades to linked `AtomicChapter` and nullifies `parent_id` on child items.

**Request**: No body.

**Responses**:
| Status | Body | Trigger |
|--------|------|---------|
| 200 OK | Empty response (or HTMX `HX-Trigger: itemDeleted`) | Deletion succeeded |
| 404 Not Found | HTML fragment: error message | `item_id` not found |

**HTMX behaviour**: The calling element uses `hx-swap="delete"` (or `outerHTML` with empty body) to remove the item row from the DOM on success.

---

## POST `/syllabus-items/{item_id}/generate-description`

**Purpose**: Generate a description for a syllabus item using the item's title and sibling context. Returns a description for user review — does not save automatically.

**Request** (form-encoded or JSON):
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | string | Yes | Non-empty |

**Responses**:
| Status | Body | Trigger |
|--------|------|---------|
| 200 OK | HTML fragment: description textarea pre-filled with generated text | Generation succeeded |
| 422 Unprocessable | HTML fragment: error message in description area | Title is empty |
| 503 Service Unavailable | HTML fragment: error message with retry option | Gemini call failed |

**HTMX target**: `hx-swap="outerHTML"` on the description field/area in the add or edit form, replacing the empty textarea with one pre-populated with the generated text. The user can edit before saving.

---

## Unchanged Endpoints (reference)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/topics/{topic_id}/syllabus` | Render full syllabus panel |
| GET | `/syllabus-items/{item_id}/children` | Lazy-load child items |
| PATCH | `/syllabus-items/{item_id}/status` | Update learning status |
