"""ChromaDB client helpers for per-topic chunk storage and similarity retrieval.

Uses the embedded persistent client (chromadb.PersistentClient) — no separate
service required. In tests, pass chromadb.EphemeralClient() instead.
"""

from __future__ import annotations

import uuid

import chromadb

from documentlm_core.config import settings


def get_chroma_client() -> chromadb.ClientAPI:
    """Return an embedded persistent ChromaDB client backed by settings.chroma_path."""
    return chromadb.PersistentClient(path=settings.chroma_path)


def _collection_name(topic_id: uuid.UUID) -> str:
    return f"topic_{topic_id.hex}"


def get_or_create_collection(
    client: chromadb.ClientAPI,
    topic_id: uuid.UUID,
) -> chromadb.Collection:
    """Get or create the per-topic collection. Idempotent."""
    return client.get_or_create_collection(name=_collection_name(topic_id))


def upsert_source_chunks(
    client: chromadb.ClientAPI,
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
    chunks: list[str],
) -> None:
    """Upsert all chunks for a source into the topic collection.

    Chunk IDs: ``{source_id.hex}_{chunk_index}``. Safe to call multiple times.
    """
    if not chunks:
        return
    collection = get_or_create_collection(client, topic_id)
    ids = [f"{source_id.hex}_{i}" for i in range(len(chunks))]
    metadatas: list[chromadb.types.Metadata] = [
        {"source_id": str(source_id), "topic_id": str(topic_id), "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)


def query_topic_chunks(
    client: chromadb.ClientAPI,
    topic_id: uuid.UUID,
    query_text: str,
    n_results: int = 10,
) -> list[str]:
    """Return up to n_results chunk texts most similar to query_text.

    Returns an empty list if the collection does not exist or has no documents.
    Never raises on empty.
    """
    try:
        collection = client.get_collection(name=_collection_name(topic_id))
    except Exception:
        return []

    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)
    results = collection.query(query_texts=[query_text], n_results=actual_n)
    docs: list[list[str]] = results.get("documents") or [[]]
    return docs[0] if docs else []


def delete_source_chunks(
    client: chromadb.ClientAPI,
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
) -> None:
    """Remove all chunks for a given source from the collection. No-op if none found."""
    try:
        collection = client.get_collection(name=_collection_name(topic_id))
    except Exception:
        return
    collection.delete(where={"source_id": str(source_id)})
