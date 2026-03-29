# Research: Source Extraction Pipeline

**Date**: 2026-03-29 | **Branch**: `003-source-extraction-pipeline`

## 1. ChromaDB — deployment and client mode

**Decision**: Use ChromaDB's embedded persistent client (`chromadb.PersistentClient(path=settings.chroma_path)`). The client runs in-process and writes to a directory on the local filesystem. No separate process or Docker service required.

**Rationale**: This is a prototype. An embedded client is the simplest possible integration — no network config, no extra container, no URL env var. The data directory is volume-mounted in Docker alongside the app container. In tests, use `chromadb.EphemeralClient()` — no filesystem state, no cleanup required.

**Alternatives considered**:

- HTTP server sidecar (`chromadb/chroma` Docker image) — rejected; unnecessary complexity for a prototype with a single app process.
- In-memory client in production — rejected; loses all indexes on restart.

**Collection naming**: One collection per topic, named `topic_{topic_id_hex}` (UUID without hyphens). Natural isolation: deleting a topic also deletes its collection.

---

## 2. ChromaDB embedding function

**Decision**: Use ChromaDB's default embedding function (`DefaultEmbeddingFunction`), which uses `all-MiniLM-L6-v2` via `sentence-transformers`. This runs in-process with the app — no external API key required.

**Rationale**: Zero configuration, no API costs, fast for prototype-scale data. The model produces 384-dimensional vectors, sufficient for semantic similarity on academic text chunks. With the embedded client the embedding runs in the same process as the app.

**Alternatives considered**:

- OpenAI `text-embedding-3-small` via ChromaDB's `OpenAIEmbeddingFunction` — rejected for prototype; requires API key management.
- Google `text-embedding-004` via `GoogleGenerativeAiEmbeddingFunction` — consistent with Gemini agents but adds another API key dependency; deferred.

---

## 3. Pipeline function design — unified extraction

**Decision**: A single `extract_and_index_source(source_id: uuid.UUID, session: AsyncSession) -> None` function in `documentlm_core/services/pipeline.py` handles all source types.

**Dispatch logic**:

```text
source_type        → extraction method
PDF_UPLOAD         → source.content already stored; skip fetch
RAW_TEXT           → source.content already stored; skip fetch
URL_SCRAPE         → nlp_utils.fetch_url_text(source.url)
YOUTUBE_TRANSCRIPT → nlp_utils.fetch_youtube_transcript(source.url)
SEARCH (has URL)   → nlp_utils.fetch_url_text(source.url)
SEARCH (DOI only)  → mark FAILED: "No URL to fetch for DOI-only source"
```

**Idempotency check**: At entry, if `source.index_status == IndexStatus.INDEXED`, return immediately without re-fetching. This satisfies FR-005.

**Error handling**: Catch all exceptions; set `source.index_status = FAILED`, `source.index_error = str(exc)`, log with traceback. Never propagate — callers must not crash on a single source failure.

---

## 4. Where pipeline is triggered

**Decision**:

| Trigger point | How |
| --- | --- |
| User-provided source (Feature 002) | `background_tasks.add_task(extract_and_index_source, source.id)` in the sources router after saving |
| Search-discovered source (Academic Scout) | Inline `await extract_and_index_source(source.id, session)` within `run_academic_scout`, after `create_source` |

**Rationale for inline in Academic Scout**: The scout already runs as a background task, so slowdown is acceptable. Firing nested background tasks from within an existing background task requires injecting `BackgroundTasks`, which is cleaner to avoid. Inline `await` is simpler and testable.

---

## 5. Chapter Scribe — source context injection

**Decision**: In `run_chapter_scribe`, before building the prompt, query ChromaDB:

```python
chunks = await query_topic_chunks(
    client,
    topic_id=topic_id,
    query_text=f"{item_title} {item_description or ''}",
    n_results=10,
)
```

If chunks are returned, prepend them to the prompt as a `"Relevant source material:"` block. If ChromaDB has no chunks for the topic, proceed with the existing prompt unchanged — the scribe degrades gracefully.

**Chunk separator**: Chunks joined with `"\n\n---\n\n"` to visually separate source excerpts in the prompt.

---

## 6. Source model additions

**Decision**: Add four columns to the `sources` table in one Alembic migration:

| Column | Type | Default | Purpose |
| --- | --- | --- | --- |
| `source_type` | `VARCHAR(20) NOT NULL` | `'SEARCH'` | Dispatch key for extraction |
| `index_status` | `VARCHAR(10) NOT NULL` | `'PENDING'` | PENDING / INDEXED / FAILED |
| `index_error` | `TEXT NULL` | — | Error message when FAILED |
| `content` | `TEXT NULL` | — | Stored extracted text |

**Note**: `pgvector` is already in `documentlm-core`'s dependencies but is not used here — all vector storage is in ChromaDB. The dependency can remain for future use.

---

## 7. nlp_utils — extraction functions needed

This feature depends on nlp_utils providing:

- `chunk_sentences(text, chunk_size=500, chunk_overlap=50)` — already exists
- `fetch_url_text(url)` — to be added in Feature 002 (`nlp_utils/fetcher.py`)
- `fetch_youtube_transcript(url_or_id)` — to be added in Feature 002 (`nlp_utils/youtube.py`)

If Feature 002 has not been implemented yet, the pipeline marks `URL_SCRAPE` and `YOUTUBE_TRANSCRIPT` sources as `FAILED` with "extraction not yet available". This keeps Feature 003 independently deployable.

---

## 8. docker-compose.yml

No `docker-compose.yml` exists yet. This feature creates it with a single `db` service only — ChromaDB runs embedded, no container needed:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: tracker
      POSTGRES_PASSWORD: tracker
      POSTGRES_DB: tracker
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

`CHROMA_PATH` defaults to `./chroma_data` in `Settings`; overridden via env var in Docker by mounting a volume to that path.
