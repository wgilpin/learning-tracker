"""Unit tests for services/chroma.py using chromadb.EphemeralClient (no filesystem)."""

from __future__ import annotations

import uuid

import chromadb
import pytest
from documentlm_core.services.chroma import (
    delete_source_chunks,
    get_or_create_collection,
    query_topic_chunks,
    upsert_source_chunks,
)


@pytest.fixture()
def chroma_client() -> chromadb.ClientAPI:
    return chromadb.EphemeralClient()


class TestGetOrCreateCollection:
    def test_creates_collection_with_correct_name(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        collection = get_or_create_collection(chroma_client, topic_id)
        assert collection.name == f"topic_{topic_id.hex}"

    def test_idempotent_second_call_returns_same_collection(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        topic_id = uuid.uuid4()
        c1 = get_or_create_collection(chroma_client, topic_id)
        c2 = get_or_create_collection(chroma_client, topic_id)
        assert c1.name == c2.name


class TestUpsertSourceChunks:
    def test_chunks_stored_with_correct_ids(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()
        chunks = ["chunk zero", "chunk one", "chunk two"]

        upsert_source_chunks(chroma_client, topic_id, source_id, chunks)

        collection = get_or_create_collection(chroma_client, topic_id)
        chunk_ids = [f"{source_id.hex}_0", f"{source_id.hex}_1", f"{source_id.hex}_2"]
        results = collection.get(ids=chunk_ids)
        assert results["documents"] == chunks

    def test_chunks_stored_with_correct_metadata(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()

        upsert_source_chunks(chroma_client, topic_id, source_id, ["only chunk"])

        collection = get_or_create_collection(chroma_client, topic_id)
        results = collection.get(ids=[f"{source_id.hex}_0"], include=["metadatas"])
        meta = results["metadatas"][0]
        assert meta["source_id"] == str(source_id)
        assert meta["topic_id"] == str(topic_id)
        assert meta["chunk_index"] == 0

    def test_upsert_is_idempotent(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()
        chunks = ["hello world"]

        upsert_source_chunks(chroma_client, topic_id, source_id, chunks)
        upsert_source_chunks(chroma_client, topic_id, source_id, chunks)

        collection = get_or_create_collection(chroma_client, topic_id)
        assert collection.count() == 1

    def test_empty_chunks_is_noop(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()

        upsert_source_chunks(chroma_client, topic_id, source_id, [])

        collection = get_or_create_collection(chroma_client, topic_id)
        assert collection.count() == 0


class TestQueryTopicChunks:
    def test_returns_relevant_chunks(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()
        chunks = [
            "machine learning algorithms classify data",
            "neural networks are a type of machine learning",
            "databases store structured information",
        ]
        upsert_source_chunks(chroma_client, topic_id, source_id, chunks)

        results = query_topic_chunks(chroma_client, topic_id, "machine learning", n_results=2)

        assert len(results) == 2
        assert all(isinstance(r, str) for r in results)

    def test_returns_empty_list_for_missing_collection(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        topic_id = uuid.uuid4()
        results = query_topic_chunks(chroma_client, topic_id, "anything")
        assert results == []

    def test_returns_empty_list_for_empty_collection(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        topic_id = uuid.uuid4()
        # Create collection but add nothing
        get_or_create_collection(chroma_client, topic_id)
        results = query_topic_chunks(chroma_client, topic_id, "anything")
        assert results == []

    def test_n_results_capped_to_collection_size(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()
        upsert_source_chunks(chroma_client, topic_id, source_id, ["only chunk"])

        results = query_topic_chunks(chroma_client, topic_id, "anything", n_results=10)
        assert len(results) == 1


class TestQueryTopicChunksWithSources:
    def test_returns_chunk_source_pairs(self, chroma_client: chromadb.ClientAPI) -> None:
        from documentlm_core.services.chroma import query_topic_chunks_with_sources

        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()
        upsert_source_chunks(chroma_client, topic_id, source_id, ["attention mechanism"])

        results = query_topic_chunks_with_sources(chroma_client, topic_id, "attention", n_results=1)

        assert len(results) == 1
        chunk_text, returned_source_id = results[0]
        assert isinstance(chunk_text, str)
        assert returned_source_id == source_id

    def test_multiple_sources_returns_correct_ids(self, chroma_client: chromadb.ClientAPI) -> None:
        from documentlm_core.services.chroma import query_topic_chunks_with_sources

        topic_id = uuid.uuid4()
        source_a = uuid.uuid4()
        source_b = uuid.uuid4()
        upsert_source_chunks(chroma_client, topic_id, source_a, ["transformer architecture"])
        upsert_source_chunks(chroma_client, topic_id, source_b, ["recurrent neural network"])

        results = query_topic_chunks_with_sources(chroma_client, topic_id, "neural network", n_results=2)

        returned_ids = {src_id for _, src_id in results}
        assert returned_ids <= {source_a, source_b}

    def test_returns_empty_list_for_missing_collection(self, chroma_client: chromadb.ClientAPI) -> None:
        from documentlm_core.services.chroma import query_topic_chunks_with_sources

        results = query_topic_chunks_with_sources(chroma_client, uuid.uuid4(), "anything")
        assert results == []

    def test_returns_empty_list_for_empty_collection(self, chroma_client: chromadb.ClientAPI) -> None:
        from documentlm_core.services.chroma import query_topic_chunks_with_sources

        topic_id = uuid.uuid4()
        get_or_create_collection(chroma_client, topic_id)
        results = query_topic_chunks_with_sources(chroma_client, topic_id, "anything")
        assert results == []


class TestDeleteSourceChunks:
    def test_removes_all_chunks_for_source(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_a = uuid.uuid4()
        source_b = uuid.uuid4()

        upsert_source_chunks(chroma_client, topic_id, source_a, ["chunk a0", "chunk a1"])
        upsert_source_chunks(chroma_client, topic_id, source_b, ["chunk b0"])

        delete_source_chunks(chroma_client, topic_id, source_a)

        collection = get_or_create_collection(chroma_client, topic_id)
        assert collection.count() == 1  # only source_b remains

    def test_noop_for_missing_collection(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_id = uuid.uuid4()
        # Should not raise
        delete_source_chunks(chroma_client, topic_id, source_id)

    def test_noop_when_source_has_no_chunks(self, chroma_client: chromadb.ClientAPI) -> None:
        topic_id = uuid.uuid4()
        source_a = uuid.uuid4()
        source_b = uuid.uuid4()

        upsert_source_chunks(chroma_client, topic_id, source_a, ["chunk a0"])
        # source_b has no chunks
        delete_source_chunks(chroma_client, topic_id, source_b)

        collection = get_or_create_collection(chroma_client, topic_id)
        assert collection.count() == 1
