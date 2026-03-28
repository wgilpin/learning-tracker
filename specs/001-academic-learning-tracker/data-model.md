# Data Model: Academic Learning Tracker App

**Branch**: `001-academic-learning-tracker`
**Date**: 2026-03-28

---

## Entities

### Topic

The root learning goal defined by the user. One Topic owns one Syllabus tree and one
VirtualBook.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, auto-generated |
| `title` | str | NOT NULL, max 500 chars |
| `description` | str \| None | nullable |
| `created_at` | datetime | NOT NULL, UTC |

**Relationships**:
- Has many `SyllabusItem` (one-to-many via `topic_id`)
- Has one `VirtualBook` (one-to-one via `topic_id`)

---

### SyllabusItem

A single concept node in the topic's learning hierarchy.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, auto-generated |
| `topic_id` | UUID | FK → Topic.id, NOT NULL |
| `title` | str | NOT NULL, max 500 chars |
| `description` | str \| None | nullable |
| `status` | SyllabusStatus | NOT NULL, default `UNRESEARCHED` |
| `display_order` | int | NOT NULL, default 0 |
| `created_at` | datetime | NOT NULL, UTC |
| `updated_at` | datetime | NOT NULL, UTC |

**SyllabusStatus** enum: `UNRESEARCHED` | `IN_PROGRESS` | `MASTERED`

**Relationships**:
- Belongs to `Topic`
- Many-to-many self-referential via `SyllabusPrerequisite` (prerequisites)
- Has at most one `AtomicChapter`

**Validation rules**:
- A SyllabusItem MUST NOT list itself as a prerequisite.
- The prerequisite graph for a Topic MUST be acyclic (validated on write).
- Status transition: any status → any status (user-controlled); blocking is enforced at the
  service layer, not the DB.

---

### SyllabusPrerequisite

Junction table encoding prerequisite relationships between SyllabusItems.

| Field | Type | Constraints |
|-------|------|-------------|
| `item_id` | UUID | FK → SyllabusItem.id, NOT NULL |
| `prerequisite_id` | UUID | FK → SyllabusItem.id, NOT NULL |

**Composite PK**: (`item_id`, `prerequisite_id`)

**Constraint**: Both `item_id` and `prerequisite_id` MUST belong to the same Topic.

---

### VirtualBook

The master document container for a Topic.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, auto-generated |
| `topic_id` | UUID | FK → Topic.id, UNIQUE, NOT NULL |
| `created_at` | datetime | NOT NULL, UTC |

**Relationships**:
- Belongs to `Topic` (one-to-one)
- Has many `AtomicChapter`
- Has many `Source` via `VirtualBookSource`

---

### AtomicChapter

A drafted chapter for one SyllabusItem.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, auto-generated |
| `virtual_book_id` | UUID | FK → VirtualBook.id, NOT NULL |
| `syllabus_item_id` | UUID | FK → SyllabusItem.id, UNIQUE, NOT NULL |
| `content` | str | NOT NULL |
| `created_at` | datetime | NOT NULL, UTC |
| `updated_at` | datetime | NOT NULL, UTC |

**Relationships**:
- Belongs to `VirtualBook`
- Belongs to `SyllabusItem` (one-to-one)
- Has many `MarginComment`
- Has many `Source` via `ChapterSource`

---

### Source

A bibliographic record with a verification status.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, auto-generated |
| `topic_id` | UUID | FK → Topic.id, NOT NULL |
| `url` | str \| None | nullable |
| `doi` | str \| None | nullable |
| `title` | str | NOT NULL |
| `authors` | list[str] | NOT NULL, stored as JSON array |
| `publication_date` | date \| None | nullable |
| `verification_status` | SourceStatus | NOT NULL, default `QUEUED` |
| `created_at` | datetime | NOT NULL, UTC |

**SourceStatus** enum: `QUEUED` | `VERIFIED` | `REJECTED`

**Constraint**: At least one of `url` or `doi` MUST be non-null.

**Deduplication key**: (`topic_id`, `doi`) when DOI present; (`topic_id`, `url`) otherwise.

**Relationships**:
- Belongs to `Topic`
- Many-to-many with `AtomicChapter` via `ChapterSource`

---

### ChapterSource

Junction table linking verified sources to the chapters that cite them.

| Field | Type | Constraints |
|-------|------|-------------|
| `chapter_id` | UUID | FK → AtomicChapter.id, NOT NULL |
| `source_id` | UUID | FK → Source.id, NOT NULL |

**Composite PK**: (`chapter_id`, `source_id`)

**Constraint**: `source_id` MUST have `verification_status = VERIFIED` at citation time.

---

### MarginComment

A user annotation anchored to a paragraph within an AtomicChapter.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK, auto-generated |
| `chapter_id` | UUID | FK → AtomicChapter.id, NOT NULL |
| `paragraph_anchor` | str | NOT NULL — a stable identifier for the target paragraph |
| `content` | str | NOT NULL |
| `response` | str \| None | nullable — filled when agent responds |
| `status` | CommentStatus | NOT NULL, default `OPEN` |
| `created_at` | datetime | NOT NULL, UTC |
| `resolved_at` | datetime \| None | nullable |

**CommentStatus** enum: `OPEN` | `RESOLVED`

---

## State Transitions

### SyllabusItem Status

```
UNRESEARCHED  ──►  IN_PROGRESS  ──►  MASTERED
      ▲                │                │
      └────────────────┘                │
      ▲                                 │
      └─────────────────────────────────┘
```

Any status transition is permitted. The service layer enforces blocking:
- Drafting a chapter requires all direct prerequisites to be `IN_PROGRESS` or `MASTERED`.

### Source Verification

```
QUEUED  ──►  VERIFIED
  │
  └──►  REJECTED
```

Only `VERIFIED` sources may be referenced in `ChapterSource`.

### MarginComment Status

```
OPEN  ──►  RESOLVED
```

Resolution is one-way; resolved comments are not reopened.

---

## Pydantic Schemas (Service Layer)

All service functions receive and return typed Pydantic models — never raw SQLAlchemy ORM
objects or plain dicts.

```python
# packages/documentlm-core/src/documentlm_core/schemas.py

class TopicCreate(BaseModel):
    title: str
    description: str | None = None

class TopicRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    created_at: datetime

class SyllabusItemCreate(BaseModel):
    topic_id: UUID
    title: str
    description: str | None = None
    prerequisite_ids: list[UUID] = []

class SyllabusItemRead(BaseModel):
    id: UUID
    topic_id: UUID
    title: str
    description: str | None
    status: SyllabusStatus
    display_order: int
    prerequisite_ids: list[UUID]
    is_blocked: bool          # derived: True if any prerequisite is UNRESEARCHED

class SyllabusItemStatusUpdate(BaseModel):
    status: SyllabusStatus

class SourceCreate(BaseModel):
    topic_id: UUID
    url: str | None = None
    doi: str | None = None
    title: str
    authors: list[str]
    publication_date: date | None = None

    @model_validator(mode="after")
    def require_url_or_doi(self) -> "SourceCreate":
        if not self.url and not self.doi:
            raise ValueError("At least one of url or doi must be provided")
        return self

class SourceRead(BaseModel):
    id: UUID
    topic_id: UUID
    url: str | None
    doi: str | None
    title: str
    authors: list[str]
    publication_date: date | None
    verification_status: SourceStatus

class ChapterRead(BaseModel):
    id: UUID
    syllabus_item_id: UUID
    content: str
    sources: list[SourceRead]
    created_at: datetime
    updated_at: datetime

class MarginCommentCreate(BaseModel):
    paragraph_anchor: str
    content: str

class MarginCommentRead(BaseModel):
    id: UUID
    chapter_id: UUID
    paragraph_anchor: str
    content: str
    response: str | None
    status: CommentStatus
    created_at: datetime
```

---

## pgvector Schema

Chapter content is chunked and embedded for RAG retrieval.

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | PK |
| `chapter_id` | UUID | FK → AtomicChapter.id, NOT NULL |
| `chunk_index` | int | NOT NULL |
| `chunk_text` | str | NOT NULL |
| `embedding` | vector(768) | NOT NULL — pgvector column |

**Index**: `ivfflat` index on `embedding` for approximate nearest-neighbour search.

---

## ER Summary

```
Topic
  ├── SyllabusItem (many, via topic_id)
  │     └── SyllabusPrerequisite (self-ref M:M)
  ├── VirtualBook (one, via topic_id)
  │     └── AtomicChapter (many, via virtual_book_id)
  │           ├── MarginComment (many, via chapter_id)
  │           ├── ChapterSource (M:M junction → Source)
  │           └── ChapterChunk / pgvector (many, via chapter_id)
  └── Source (many, via topic_id)
```
