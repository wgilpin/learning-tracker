# Data Model: Source Extraction Pipeline

**Date**: 2026-03-29 | **Branch**: `003-source-extraction-pipeline`

---

## PostgreSQL changes

### New columns on `sources`

| Column | SQLAlchemy type | Nullable | Default | Notes |
| --- | --- | --- | --- | --- |
| `source_type` | `String(20) NOT NULL` | No | `'SEARCH'` | See `SourceType` enum |
| `index_status` | `String(10) NOT NULL` | No | `'PENDING'` | See `IndexStatus` enum |
| `index_error` | `Text` | Yes | — | Populated on FAILED; cleared on re-index |
| `content` | `Text` | Yes | — | Extracted full text; NULL until indexed or for SEARCH sources with no URL |

### New enums (schemas.py)

```python
class SourceType(StrEnum):
    PDF_UPLOAD         = "PDF_UPLOAD"
    URL_SCRAPE         = "URL_SCRAPE"
    YOUTUBE_TRANSCRIPT = "YOUTUBE_TRANSCRIPT"
    RAW_TEXT           = "RAW_TEXT"
    SEARCH             = "SEARCH"          # existing search-discovered sources

class IndexStatus(StrEnum):
    PENDING = "PENDING"    # not yet processed
    INDEXED = "INDEXED"    # extracted + embedded in ChromaDB
    FAILED  = "FAILED"     # extraction or embedding failed
```

### State transitions

```text
PENDING ──(extraction succeeds)──► INDEXED
PENDING ──(extraction fails)──────► FAILED
FAILED  ──(manual re-trigger)─────► PENDING → INDEXED or FAILED
```

### Updated SourceRead schema

```python
class SourceRead(BaseModel):
    id: UUID
    topic_id: UUID
    source_type: SourceType          # NEW
    index_status: IndexStatus        # NEW
    index_error: str | None          # NEW
    url: str | None
    doi: str | None
    title: str
    authors: list[str]
    publication_date: date | None
    verification_status: SourceStatus
    content: str | None              # NEW (may be None for unindexed SEARCH sources)

    model_config = {"from_attributes": True}
```

### Alembic migration: `0003_add_source_index_fields.py`

```sql
-- Up
ALTER TABLE sources
  ADD COLUMN source_type   VARCHAR(20)  NOT NULL DEFAULT 'SEARCH',
  ADD COLUMN index_status  VARCHAR(10)  NOT NULL DEFAULT 'PENDING',
  ADD COLUMN index_error   TEXT,
  ADD COLUMN content       TEXT;

-- Down
ALTER TABLE sources
  DROP COLUMN content,
  DROP COLUMN index_error,
  DROP COLUMN index_status,
  DROP COLUMN source_type;
```

---

## ChromaDB schema

### Collections

One collection per topic: `topic_{topic_id.hex}` (UUID without hyphens, e.g. `topic_550e8400e29b41d4a716446655440000`).

Deleted when the topic is deleted (caller's responsibility).

### Document format per chunk

| Field | Value |
| --- | --- |
| `id` | `"{source_id_hex}_{chunk_index}"` — unique within collection |
| `document` | Chunk text (~500 chars) |
| `metadata.source_id` | `str(source_id)` |
| `metadata.topic_id` | `str(topic_id)` |
| `metadata.chunk_index` | `int` |

### Query parameters

- `query_texts`: `[f"{item_title} {item_description}"]`
- `n_results`: `10`
- Returns: list of document strings (the chunks), ranked by cosine similarity

---

## New service: `documentlm_core/services/chroma.py`

```python
import chromadb
from chromadb import AsyncClientAPI

async def get_chroma_client() -> AsyncClientAPI:
    """Return an async ChromaDB HTTP client pointed at settings.chroma_url."""

async def get_or_create_collection(
    client: AsyncClientAPI,
    topic_id: uuid.UUID,
) -> chromadb.AsyncCollection:
    """Get or create the per-topic collection."""

async def upsert_source_chunks(
    client: AsyncClientAPI,
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
    chunks: list[str],
) -> None:
    """Upsert all chunks for a source into the topic collection."""

async def query_topic_chunks(
    client: AsyncClientAPI,
    topic_id: uuid.UUID,
    query_text: str,
    n_results: int = 10,
) -> list[str]:
    """Return up to n_results chunk texts most similar to query_text."""

async def delete_source_chunks(
    client: AsyncClientAPI,
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
) -> None:
    """Remove all chunks for a given source from the collection."""
```

---

## New service: `documentlm_core/services/pipeline.py`

```python
async def extract_and_index_source(
    source_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """Extract text from a source and upsert chunks into ChromaDB.

    Idempotent: returns immediately if source.index_status == INDEXED.
    On any failure: sets index_status=FAILED, logs with traceback, does not raise.
    """
```

Dispatch table (internal):

| `source_type` | Extraction method |
| --- | --- |
| `PDF_UPLOAD` | `source.content` already stored — skip fetch, go straight to chunking |
| `RAW_TEXT` | `source.content` already stored — skip fetch |
| `URL_SCRAPE` | `await fetch_url_text(source.url)` |
| `YOUTUBE_TRANSCRIPT` | `await fetch_youtube_transcript(source.url)` |
| `SEARCH` (has URL) | `await fetch_url_text(source.url)` |
| `SEARCH` (DOI only) | Mark FAILED: "No URL to fetch for DOI-only source" |

---

## Modified: `documentlm_core/agents/chapter_scribe.py`

`run_chapter_scribe` gains a ChromaDB retrieval step before prompt construction:

```python
async def run_chapter_scribe(
    item_id: uuid.UUID,
    item_title: str,
    item_description: str | None,      # NEW parameter
    topic_id: uuid.UUID,
    session: AsyncSession,
) -> str:
    ...
    # NEW: retrieve relevant chunks
    chroma_client = await get_chroma_client()
    query = f"{item_title} {item_description or ''}".strip()
    source_chunks = await query_topic_chunks(chroma_client, topic_id, query, n_results=10)

    prompt_parts = [f"Topic: {item_title}"]
    if source_chunks:
        prompt_parts.append(
            "Relevant source material:\n\n" + "\n\n---\n\n".join(source_chunks)
        )
    # existing prior-chapter context follows...
```

---

## Modified: `documentlm_core/agents/academic_scout.py`

After each successful `create_source`, call the pipeline inline:

```python
source = await create_source(session, SourceCreate(...))
await extract_and_index_source(source.id, session)
```

---

## Modified: `apps/api/templates/sources/_row.html`

Add index status badge alongside existing verification badge:

```html
<span class="status-badge status-index-{{ source.index_status | lower }}">
  {{ source.index_status }}
</span>
```

---

## config.py addition

```python
chroma_path: str = Field(default="./chroma_data", alias="CHROMA_PATH")
```
