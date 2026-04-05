# Data Model: Lesson Illustrations

**Feature**: 008-lesson-illustrations  
**Date**: 2026-04-04

---

## New Table: `chapter_illustrations`

Stores generated illustration images indexed by chapter and paragraph position.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK | Unique identifier |
| `chapter_id` | `UUID` | FK → `atomic_chapters.id` ON DELETE CASCADE | Owning chapter |
| `paragraph_index` | `INTEGER` | NOT NULL | 1-based index matching `para-N` anchor system |
| `image_data` | `BYTEA` | NOT NULL | Raw image bytes from Gemini |
| `image_mime_type` | `VARCHAR(64)` | NOT NULL | e.g., `"image/png"`, `"image/jpeg"` |
| `image_description` | `TEXT` | NOT NULL | Description used to generate the image |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL | Generation timestamp |

**Unique constraint**: `(chapter_id, paragraph_index)` — at most one illustration per paragraph per chapter.

---

## New Pydantic Schemas

### `ParagraphAssessment`

Represents the structured result of the LLM assessment call for a single paragraph.

```
ParagraphAssessment:
  requires_image: bool
  image_description: str   # Empty string when requires_image is False
```

### `IllustrationRead`

Public-facing read schema for a persisted illustration.

```
IllustrationRead:
  id: UUID
  chapter_id: UUID
  paragraph_index: int
  image_mime_type: str
  image_description: str
  created_at: datetime
  # image_data is NOT included — served via dedicated endpoint
```

---

## New SQLAlchemy ORM Model: `ChapterIllustration`

Belongs in `packages/documentlm-core/src/documentlm_core/db/models.py`.

```
ChapterIllustration:
  __tablename__ = "chapter_illustrations"

  id: Mapped[uuid.UUID]              # PK, SQLUUID(as_uuid=True)
  chapter_id: Mapped[uuid.UUID]      # FK → atomic_chapters.id, ON DELETE CASCADE
  paragraph_index: Mapped[int]       # 1-based
  image_data: Mapped[bytes]          # LargeBinary
  image_mime_type: Mapped[str]       # VARCHAR(64)
  image_description: Mapped[str]     # Text
  created_at: Mapped[datetime]

  # Relationship
  chapter: Mapped[AtomicChapter]     # back_populates="illustrations"

  # Unique constraint on (chapter_id, paragraph_index)
```

`AtomicChapter` gains a new relationship:
```
illustrations: Mapped[list[ChapterIllustration]]  # relationship, cascade="all, delete-orphan"
```

---

## New Config Field

Added to `packages/documentlm-core/src/documentlm_core/config.py`:

```
Settings:
  illustration_model: str = "gemini-3.1-flash-image-preview"
  # alias: ILLUSTRATION_MODEL
  # .env variable: ILLUSTRATION_MODEL
```

---

## Migration

A new Alembic migration creates the `chapter_illustrations` table. The migration is additive — no existing tables are modified except adding the `illustrations` relationship (handled by SQLAlchemy, no migration needed for the Python relationship attribute).

---

## Entity Relationships

```
atomic_chapters (existing)
  └─── chapter_illustrations (new, 1:many, cascade delete)
         ├── paragraph_index: int   → matches para-N anchor in template
         ├── image_data: bytes      → served via GET endpoint
         └── image_mime_type: str   → Content-Type header
```

---

## State Transitions

```
[Chapter created]
      │
      ▼
[Illustration pipeline triggered as background task]
      │
      ├─ For each paragraph:
      │     ├─ [Assess paragraph] → ParagraphAssessment
      │     │     ├─ requires_image=False → skip (no DB record)
      │     │     └─ requires_image=True
      │     │           └─ [Generate image] → bytes
      │     │                 ├─ Success → [Persist ChapterIllustration]
      │     │                 └─ Failure → log ERROR, skip paragraph
      │
      └─ [Chapter renders with available illustrations]
             (paragraphs without illustrations render as text-only)
```
