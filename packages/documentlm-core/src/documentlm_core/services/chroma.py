"""ChromaDB client helpers for per-source chunk storage and similarity retrieval.

Collections are keyed per-source: ``source_{source_id.hex}``.
This enables global source deduplication — two users sharing the same source
document share a single ChromaDB collection.

In tests, pass chromadb.EphemeralClient() instead of the persistent client.
"""

from __future__ import annotations

import uuid

import chromadb

from documentlm_core.config import settings


def get_chroma_client() -> chromadb.ClientAPI:
    """Return an embedded persistent ChromaDB client backed by settings.chroma_path."""
    return chromadb.PersistentClient(path=settings.chroma_path)


def _collection_name(source_id: uuid.UUID) -> str:
    return f"source_{source_id.hex}"


def get_or_create_source_collection(
    client: chromadb.ClientAPI,
    source_id: uuid.UUID,
) -> chromadb.Collection:
    """Get or create the per-source collection. Idempotent."""
    return client.get_or_create_collection(name=_collection_name(source_id))


def upsert_source_chunks(
    client: chromadb.ClientAPI,
    source_id: uuid.UUID,
    chunks: list[str],
) -> None:
    """Upsert all chunks for a source into its own collection.

    Chunk IDs: ``{source_id.hex}_{chunk_index}``. Safe to call multiple times.
    """
    if not chunks:
        return
    collection = get_or_create_source_collection(client, source_id)
    ids = [f"{source_id.hex}_{i}" for i in range(len(chunks))]
    metadatas: list[chromadb.types.Metadata] = [
        {"source_id": str(source_id), "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)


def query_topic_chunks_with_sources(
    client: chromadb.ClientAPI,
    source_ids: list[uuid.UUID],
    query_text: str,
    n_results: int = 10,
) -> list[tuple[str, uuid.UUID]]:
    """Return (chunk_text, source_id) pairs most similar to query_text.

    Queries each source's collection and merges results.
    Returns an empty list if no collections exist or no chunks found.
    """
    if not source_ids:
        return []

    all_pairs: list[tuple[str, uuid.UUID, float]] = []

    for source_id in source_ids:
        try:
            collection = client.get_collection(name=_collection_name(source_id))
        except Exception:
            continue

        count = collection.count()
        if count == 0:
            continue

        actual_n = min(n_results, count)
        try:
            results = collection.query(
                query_texts=[query_text],
                n_results=actual_n,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            continue

        docs: list[str] = (results.get("documents") or [[]])[0]
        distances: list[float] = (results.get("distances") or [[]])[0]

        for doc, dist in zip(docs, distances):
            all_pairs.append((doc, source_id, dist))

    # Sort by distance (ascending = most similar first), take top n_results
    all_pairs.sort(key=lambda x: x[2])
    return [(doc, src_id) for doc, src_id, _ in all_pairs[:n_results]]


def delete_source_collection(
    client: chromadb.ClientAPI,
    source_id: uuid.UUID,
) -> None:
    """Delete the ChromaDB collection for a source. No-op if it doesn't exist."""
    try:
        client.delete_collection(name=_collection_name(source_id))
    except Exception:
        pass


def delete_source_chunks(
    client: chromadb.ClientAPI,
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
) -> None:
    """Delete the source collection. topic_id is ignored (collections are per-source now)."""
    delete_source_collection(client, source_id)
