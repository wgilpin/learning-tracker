# Data Model: Topic Source Upload

**Date**: 2026-03-29 | **Branch**: `002-topic-source-upload`

## Source model changes

### New columns on `sources`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `source_type` | `VARCHAR(20)` | NOT NULL | `'SEARCH'` | See `SourceType` enum below |
| `is_primary` | `BOOLEAN` | NOT NULL | `false` | True for all user-provided sources |
| `content` | `TEXT` | NULL | — | Extracted text; NULL for bibliographic-only sources |
| `content_hash` | `VARCHAR(64)` | NULL | — | SHA-256 hex of content; used to deduplicate raw-text sources |

### SourceType enum (new)

```python
class SourceType(StrEnum):
    PDF_UPLOAD        = "PDF_UPLOAD"
    URL_SCRAPE        = "URL_SCRAPE"
    YOUTUBE_TRANSCRIPT = "YOUTUBE_TRANSCRIPT"
    RAW_TEXT          = "RAW_TEXT"
    SEARCH            = "SEARCH"   # existing search-discovered sources
```

### Updated deduplication rules

- `SEARCH` / `URL_SCRAPE` / `YOUTUBE_TRANSCRIPT`: deduplicated by `(topic_id, url)` — existing `uq_source_topic_url` constraint applies.
- `PDF_UPLOAD` / `RAW_TEXT`: deduplicated by `(topic_id, content_hash)` — new `uq_source_topic_content_hash` constraint.

### Updated `SourceCreate` schema

The existing `@model_validator(require_url_or_doi)` is relaxed: it only applies when `source_type == SourceType.SEARCH`. Primary source types (`PDF_UPLOAD`, `RAW_TEXT`) require `content`; `URL_SCRAPE` and `YOUTUBE_TRANSCRIPT` require `url`.

```python
class PrimarySourceCreate(BaseModel):
    topic_id: UUID
    source_type: SourceType
    title: str
    content: str           # extracted text (always required for primary)
    url: str | None = None # required for URL_SCRAPE and YOUTUBE_TRANSCRIPT
    content_hash: str      # SHA-256 hex of content
    authors: list[str] = []
```

### New read schema

```python
class SourceRead(BaseModel):          # extends existing
    id: UUID
    topic_id: UUID
    source_type: SourceType           # NEW
    is_primary: bool                  # NEW
    title: str
    url: str | None
    doi: str | None
    authors: list[str]
    publication_date: date | None
    verification_status: SourceStatus
    content: str | None               # NEW (may be None for SEARCH)
```

---

## Alembic migration

One new migration: `0004_add_primary_source_fields.py`

```sql
-- Up
ALTER TABLE sources ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'SEARCH';
ALTER TABLE sources ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE sources ADD COLUMN content TEXT;
ALTER TABLE sources ADD COLUMN content_hash VARCHAR(64);

ALTER TABLE sources ADD CONSTRAINT uq_source_topic_content_hash
    UNIQUE (topic_id, content_hash);

-- Down
ALTER TABLE sources DROP CONSTRAINT uq_source_topic_content_hash;
ALTER TABLE sources DROP COLUMN content_hash;
ALTER TABLE sources DROP COLUMN content;
ALTER TABLE sources DROP COLUMN is_primary;
ALTER TABLE sources DROP COLUMN source_type;
```

---

## nlp_utils extensions

### `nlp_utils/fetcher.py` — new functions

```python
def extract_pdf_text_from_bytes(data: bytes) -> str:
    """Extract text from raw PDF bytes via pypdf.

    Raises ValueError if no text extracted (image-only PDF).
    """

async def fetch_url_text(url: str, timeout: float = 30.0) -> str:
    """Fetch a URL and return clean extracted text.

    Uses httpx + extract_clean_html from nlp_utils.html.
    Raises httpx.HTTPError on network/HTTP failure.
    Raises ValueError if extracted text is empty.
    """
```

### `nlp_utils/youtube.py` — new module

```python
async def fetch_youtube_transcript(url_or_id: str) -> tuple[str, str]:
    """Fetch transcript for a YouTube video.

    Args:
        url_or_id: Full YouTube URL or bare video ID.

    Returns:
        (title, transcript_text) — title falls back to video_id if unavailable.

    Raises:
        ValueError: if no transcript is available or video cannot be found.
    """
```

### `nlp_utils/__init__.py` additions

```python
from nlp_utils.fetcher import extract_pdf_text_from_bytes, fetch_url_text
from nlp_utils.youtube import fetch_youtube_transcript
```

---

## Service layer — new / modified

### `documentlm_core/services/source.py`

**New function**:

```python
async def create_primary_source(
    session: AsyncSession,
    data: PrimarySourceCreate,
) -> tuple[SourceRead, bool]:
    """Create a primary source with deduplication.

    Returns (source, was_duplicate). Deduplicate by:
    - content_hash for PDF_UPLOAD / RAW_TEXT
    - url for URL_SCRAPE / YOUTUBE_TRANSCRIPT

    Logs and returns existing record on duplicate (no error raised).
    """
```

**Modified**:
- `list_sources` gains optional `primary_only: bool = False` parameter.

### `documentlm_core/services/source.py` — content hash utility

```python
def compute_content_hash(text: str) -> str:
    """Return SHA-256 hex digest of text encoded as UTF-8."""
```

---

## Agent modifications

### `documentlm_core/agents/syllabus_architect.py`

`run_syllabus_architect` signature change:

```python
async def run_syllabus_architect(
    topic_id: uuid.UUID,
    topic_title: str,
    tools: SyllabusToolsProtocol,
    primary_source_texts: list[str] | None = None,   # NEW
) -> list[uuid.UUID]:
```

Prompt construction:
- If `primary_source_texts` is `None` or empty → existing free-generation prompt unchanged.
- If exactly one entry → prepend: `"Use the following provided syllabus exactly as the structure (do not invent new sections):\n\n{text}"`.
- If multiple entries → prepend all texts with the instruction to synthesise a single coherent structure from them.

### `documentlm_core/agents/academic_scout.py`

`run_academic_scout` gains a guard:

```python
async def run_academic_scout(
    topic_id: uuid.UUID,
    topic_title: str,
    session: AsyncSession,
) -> list[uuid.UUID]:
    # NEW: load primary sources first and log them
    primary_sources = await list_sources(session, topic_id, primary_only=True)
    if primary_sources:
        logger.info(
            "Academic Scout: %d primary sources present — processing before search",
            len(primary_sources),
        )
    # ... existing search logic follows unchanged
```

---

## API layer — new endpoints

### `apps/api/src/api/routers/sources.py` (new file)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/topics/{topic_id}/sources/extract` | Upload/submit one source; extract immediately; return source card HTML (HTMX) |
| `DELETE` | `/topics/{topic_id}/sources/{source_id}` | Remove a source; return empty response with HX-Trigger to refresh list |

#### `POST /topics/{topic_id}/sources/extract` — form fields

| Field | Type | Required when |
|-------|------|--------------|
| `source_type` | `str` | always |
| `file` | `UploadFile` | `source_type == PDF_UPLOAD` |
| `url` | `str` | `source_type in {URL_SCRAPE, YOUTUBE_TRANSCRIPT}` |
| `text` | `str` | `source_type == RAW_TEXT` |

Response: HTMX partial — a `<div>` source card showing title, type badge, truncated content preview, and a remove button.

### Modified: `apps/api/src/api/routers/topics.py`

- `POST /topics` redirects to `/topics/{id}/sources` (new intermediate page) instead of directly to the topic detail page.
- New `GET /topics/{id}/sources` — source intake page showing: current primary sources, add-source form with tabs (PDF / URL / YouTube / Text), and a "Generate syllabus" button.
- `POST /topics/{id}/generate` — triggers `_run_syllabus_architect` background task with primary source texts; redirects to `/topics/{id}`.

---

## Workflow summary

```
POST /topics (title, description)
  → creates Topic
  → 303 redirect to GET /topics/{id}/sources

GET /topics/{id}/sources
  → shows source intake UI (HTMX tabs)

[user adds sources, each triggers:]
POST /topics/{id}/sources/extract
  → extract text (nlp_utils)
  → create_primary_source()
  → return HTMX source card

POST /topics/{id}/generate
  → load primary source texts from DB
  → background_tasks.add_task(_run_syllabus_architect, ..., primary_source_texts)
  → background_tasks.add_task(_run_academic_scout, ...)   ← runs after, sees primary sources
  → 303 redirect to GET /topics/{id}
```
