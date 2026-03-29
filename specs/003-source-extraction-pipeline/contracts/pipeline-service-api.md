# Contract: Source Extraction Pipeline — Internal Service API

These are the internal Python function signatures exposed by the pipeline and ChromaDB services. Callers (agents, routers) must honour these contracts.

## `services/pipeline.py`

```python
async def extract_and_index_source(
    source_id: uuid.UUID,
    session: AsyncSession,
) -> None
```

**Behaviour**:
- Idempotent: no-op if `source.index_status == IndexStatus.INDEXED`.
- On success: `source.index_status = INDEXED`, `source.content` populated (if not already), chunks upserted to ChromaDB.
- On failure: `source.index_status = FAILED`, `source.index_error = str(exc)`, exception logged with traceback. Never raises.
- Flushes DB changes within the provided `session`; does NOT commit — caller is responsible for commit.

**Must NOT be called** with a session that has uncommitted changes to the same source row (race condition risk). Callers should commit before handing off to a background task.

---

## `services/chroma.py`

```python
async def get_chroma_client() -> chromadb.AsyncClientAPI
```
Returns a stateless async client; safe to call per-request. No connection pooling needed at prototype scale.

---

```python
async def get_or_create_collection(
    client: chromadb.AsyncClientAPI,
    topic_id: uuid.UUID,
) -> chromadb.AsyncCollection
```
Collection name: `topic_{topic_id.hex}`. Uses ChromaDB default embedding function. Idempotent.

---

```python
async def upsert_source_chunks(
    client: chromadb.AsyncClientAPI,
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
    chunks: list[str],
) -> None
```
Chunk IDs: `f"{source_id.hex}_{i}"` for `i` in `range(len(chunks))`. Safe to call multiple times (upsert semantics).

---

```python
async def query_topic_chunks(
    client: chromadb.AsyncClientAPI,
    topic_id: uuid.UUID,
    query_text: str,
    n_results: int = 10,
) -> list[str]
```
Returns empty list if the collection does not exist or has no documents. Never raises on empty.

---

```python
async def delete_source_chunks(
    client: chromadb.AsyncClientAPI,
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
) -> None
```
Deletes all chunks where `metadata.source_id == str(source_id)`. No-op if none found.
