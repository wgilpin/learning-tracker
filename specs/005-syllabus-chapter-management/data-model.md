# Data Model: Syllabus Chapter Management

**Branch**: `005-syllabus-chapter-management` | **Date**: 2026-04-01

## Existing Models (unchanged)

### `SyllabusItem` (DB table: `syllabus_items`)

No migration required. All required fields already exist.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID | No | PK |
| `topic_id` | UUID FK → `topics.id` | No | Cascade delete |
| `parent_id` | UUID FK → `syllabus_items.id` | Yes | Self-referential; SET NULL on delete |
| `title` | String(500) | No | Non-empty enforced at service layer |
| `description` | Text | Yes | Optional; can be empty |
| `status` | String(20) | No | `UNRESEARCHED` \| `IN_PROGRESS` \| `MASTERED` |
| `created_at` | DateTime(tz) | No | Set on insert |
| `updated_at` | DateTime(tz) | No | Set on insert; updated on change |

**Deletion cascade behaviour** (already in schema):
- Deleting a `SyllabusItem` cascades to its `AtomicChapter` (via `ondelete="CASCADE"` on `atomic_chapters.syllabus_item_id`).
- Deleting a parent `SyllabusItem` sets `parent_id = NULL` on child items (via `ondelete="SET NULL"`).

**"Has associated content" definition**: A `SyllabusItem` has associated content if it has a linked `AtomicChapter` record OR if it has any children (`children` relationship is non-empty).

---

## New Pydantic Schemas

### `SyllabusItemUpdate`
Used for `PATCH /syllabus-items/{item_id}`.

```python
class SyllabusItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
```

Validation rules:
- If `title` is provided, it MUST be non-empty after stripping whitespace.
- At least one field must be non-None (enforced by service).

---

### `DescriptionGenerateRequest`
Used for `POST /syllabus-items/{item_id}/generate-description`.

```python
class DescriptionGenerateRequest(BaseModel):
    title: str
```

Validation rules:
- `title` MUST be non-empty.

---

### `GeneratedDescriptionRead`
Response from the generate endpoint.

```python
class GeneratedDescriptionRead(BaseModel):
    description: str
```

---

## New Service Functions

All in `documentlm_core.services.syllabus`.

### `update_syllabus_item`
```python
async def update_syllabus_item(
    session: AsyncSession,
    item_id: UUID,
    update: SyllabusItemUpdate,
) -> SyllabusItemRead
```
- Loads item; raises `ValueError` if not found.
- Updates only provided fields (partial update semantics).
- Strips whitespace from title; raises `ValueError` if title becomes empty.
- Returns updated `SyllabusItemRead`.

---

### `delete_syllabus_item`
```python
async def delete_syllabus_item(
    session: AsyncSession,
    item_id: UUID,
) -> None
```
- Loads item; raises `ValueError` if not found.
- Deletes item; cascade handles `AtomicChapter` and child `parent_id` nullification.

---

### `has_associated_content`
```python
async def has_associated_content(
    session: AsyncSession,
    item_id: UUID,
) -> bool
```
- Returns `True` if item has a linked `AtomicChapter` OR has non-empty `children`.
- Used to decide whether delete confirmation shows the extra warning.

---

### `generate_item_description`
```python
async def generate_item_description(
    session: AsyncSession,
    item_id: UUID,
    title: str,
) -> str
```
- Fetches topic context: loads the `SyllabusItem` to get `topic_id` and `parent_id`; queries sibling items (same `parent_id`) for their titles and descriptions.
- Builds a single-shot prompt including: the syllabus context (sibling items) and the new item's title.
- Calls Gemini via `google.generativeai` (same client setup as existing code) with no tools.
- Returns the generated description string.
- Raises `RuntimeError` on generation failure (logged with traceback before raising).

---

## State Transitions

`SyllabusItem.status` transitions are unchanged and handled by the existing `PATCH /syllabus-items/{item_id}/status` route. New CRUD operations do not modify status.

A newly created `SyllabusItem` always starts with `status = UNRESEARCHED`.
