"""Unit tests for services/chroma.py using chromadb.EphemeralClient (no filesystem)."""

from __future__ import annotations

import uuid

import chromadb
import pytest
from documentlm_core.services.chroma import (
    delete_source_chunks,
    delete_source_collection,
    get_or_create_source_collection,
    query_topic_chunks_with_sources,
    upsert_source_chunks,
)


@pytest.fixture()
def chroma_client() -> chromadb.ClientAPI:
    return chromadb.EphemeralClient()


class TestGetOrCreateSourceCollection:
    def test_creates_collection_with_correct_name(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()
        collection = get_or_create_source_collection(chroma_client, source_id)
        assert collection.name == f"source_{source_id.hex}"

    def test_idempotent_second_call_returns_same_collection(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        source_id = uuid.uuid4()
        c1 = get_or_create_source_collection(chroma_client, source_id)
        c2 = get_or_create_source_collection(chroma_client, source_id)
        assert c1.name == c2.name


class TestUpsertSourceChunks:
    def test_chunks_stored_with_correct_ids(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()
        chunks = ["chunk zero", "chunk one", "chunk two"]

        upsert_source_chunks(chroma_client, source_id, chunks)

        collection = get_or_create_source_collection(chroma_client, source_id)
        chunk_ids = [f"{source_id.hex}_0", f"{source_id.hex}_1", f"{source_id.hex}_2"]
        results = collection.get(ids=chunk_ids)
        assert results["documents"] == chunks

    def test_chunks_stored_with_correct_metadata(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()

        upsert_source_chunks(chroma_client, source_id, ["only chunk"])

        collection = get_or_create_source_collection(chroma_client, source_id)
        results = collection.get(ids=[f"{source_id.hex}_0"], include=["metadatas"])
        meta = results["metadatas"][0]
        assert meta["source_id"] == str(source_id)
        assert meta["chunk_index"] == 0

    def test_upsert_is_idempotent(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()
        chunks = ["hello world"]

        upsert_source_chunks(chroma_client, source_id, chunks)
        upsert_source_chunks(chroma_client, source_id, chunks)

        collection = get_or_create_source_collection(chroma_client, source_id)
        assert collection.count() == 1

    def test_empty_chunks_is_noop(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()

        upsert_source_chunks(chroma_client, source_id, [])

        # Collection should not be created
        collections = chroma_client.list_collections()
        names = [c.name for c in collections]
        assert f"source_{source_id.hex}" not in names


class TestQueryTopicChunksWithSources:
    def test_returns_chunk_source_pairs(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()
        upsert_source_chunks(chroma_client, source_id, ["attention mechanism"])

        results = query_topic_chunks_with_sources(
            chroma_client, [source_id], "attention", n_results=1
        )

        assert len(results) == 1
        chunk_text, returned_source_id = results[0]
        assert isinstance(chunk_text, str)
        assert returned_source_id == source_id

    def test_multiple_sources_returns_correct_ids(self, chroma_client: chromadb.ClientAPI) -> None:
        source_a = uuid.uuid4()
        source_b = uuid.uuid4()
        upsert_source_chunks(chroma_client, source_a, ["transformer architecture"])
        upsert_source_chunks(chroma_client, source_b, ["recurrent neural network"])

        results = query_topic_chunks_with_sources(
            chroma_client, [source_a, source_b], "neural network", n_results=2
        )

        returned_ids = {src_id for _, src_id in results}
        assert returned_ids <= {source_a, source_b}

    def test_returns_empty_list_for_missing_collection(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        results = query_topic_chunks_with_sources(
            chroma_client, [uuid.uuid4()], "anything"
        )
        assert results == []

    def test_returns_empty_list_for_empty_source_ids(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        results = query_topic_chunks_with_sources(chroma_client, [], "anything")
        assert results == []

    def test_n_results_capped_to_collection_size(
        self, chroma_client: chromadb.ClientAPI
    ) -> None:
        source_id = uuid.uuid4()
        upsert_source_chunks(chroma_client, source_id, ["only chunk"])

        results = query_topic_chunks_with_sources(
            chroma_client, [source_id], "anything", n_results=10
        )
        assert len(results) == 1


class TestDeleteSourceCollection:
    def test_removes_collection(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()
        upsert_source_chunks(chroma_client, source_id, ["chunk"])

        delete_source_collection(chroma_client, source_id)

        collections = chroma_client.list_collections()
        names = [c.name for c in collections]
        assert f"source_{source_id.hex}" not in names

    def test_noop_for_missing_collection(self, chroma_client: chromadb.ClientAPI) -> None:
        # Should not raise
        delete_source_collection(chroma_client, uuid.uuid4())


class TestDeleteSourceChunks:
    def test_removes_source_collection(self, chroma_client: chromadb.ClientAPI) -> None:
        source_id = uuid.uuid4()
        topic_id = uuid.uuid4()
        upsert_source_chunks(chroma_client, source_id, ["chunk"])

        delete_source_chunks(chroma_client, topic_id, source_id)

        collections = chroma_client.list_collections()
        names = [c.name for c in collections]
        assert f"source_{source_id.hex}" not in names

    def test_noop_for_missing_collection(self, chroma_client: chromadb.ClientAPI) -> None:
        # Should not raise
        delete_source_chunks(chroma_client, uuid.uuid4(), uuid.uuid4())
