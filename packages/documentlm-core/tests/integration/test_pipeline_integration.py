"""Integration tests for the source extraction pipeline.

Uses a real PostgreSQL session (via conftest fixtures) and chromadb.EphemeralClient
so no filesystem state is created or leaked between tests.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import chromadb
import pytest
from documentlm_core.schemas import IndexStatus, SourceType
from documentlm_core.services.chroma import (
    query_topic_chunks,
    upsert_source_chunks,
)
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
class TestPipelineEndToEnd:
    @pytest.mark.asyncio
    async def test_search_source_indexed_after_pipeline(
        self, async_session: AsyncSession
    ) -> None:
        """A SEARCH source with a URL is INDEXED after extract_and_index_source runs."""
        from documentlm_core.db.models import Source, Topic
        from documentlm_core.services.pipeline import extract_and_index_source

        topic = Topic(title="Test Topic")
        async_session.add(topic)
        await async_session.flush()

        source = Source(
            topic_id=topic.id,
            source_type=SourceType.SEARCH,
            url="https://example.com/paper",
            title="A Paper",
            authors=[],
        )
        async_session.add(source)
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()
        with (
            patch(
                "documentlm_core.services.pipeline.get_chroma_client",
                return_value=ephemeral,
            ),
            patch(
                "documentlm_core.services.pipeline._fetch_url",
                new=AsyncMock(
                    return_value="This is the extracted paper content about machine learning."
                ),
            ),
        ):
            await extract_and_index_source(source.id, async_session)

        assert source.index_status == IndexStatus.INDEXED
        assert source.content is not None

        chunks = query_topic_chunks(ephemeral, topic.id, "machine learning", n_results=10)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_failed_extraction_does_not_block_other_sources(
        self, async_session: AsyncSession
    ) -> None:
        """A source that fails extraction is marked FAILED; pipeline does not raise."""
        from documentlm_core.db.models import Source, Topic
        from documentlm_core.services.pipeline import extract_and_index_source

        topic = Topic(title="Test Topic 2")
        async_session.add(topic)
        await async_session.flush()

        source = Source(
            topic_id=topic.id,
            source_type=SourceType.URL_SCRAPE,
            url="https://broken.example",
            title="Broken Source",
            authors=[],
        )
        async_session.add(source)
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()
        with (
            patch(
                "documentlm_core.services.pipeline.get_chroma_client",
                return_value=ephemeral,
            ),
            patch(
                "documentlm_core.services.pipeline._fetch_url",
                new=AsyncMock(side_effect=RuntimeError("connection refused")),
            ),
        ):
            # Must not raise
            await extract_and_index_source(source.id, async_session)

        assert source.index_status == IndexStatus.FAILED
        assert source.index_error is not None

    @pytest.mark.asyncio
    async def test_doi_only_search_source_marked_failed(
        self, async_session: AsyncSession
    ) -> None:
        """A SEARCH source with only a DOI (no URL) is marked FAILED immediately."""
        from documentlm_core.db.models import Source, Topic
        from documentlm_core.services.pipeline import extract_and_index_source

        topic = Topic(title="DOI Topic")
        async_session.add(topic)
        await async_session.flush()

        source = Source(
            topic_id=topic.id,
            source_type=SourceType.SEARCH,
            doi="10.1234/example",
            title="DOI Paper",
            authors=[],
        )
        async_session.add(source)
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()
        with patch(
            "documentlm_core.services.pipeline.get_chroma_client",
            return_value=ephemeral,
        ):
            await extract_and_index_source(source.id, async_session)

        assert source.index_status == IndexStatus.FAILED
        assert "DOI-only" in (source.index_error or "")


@pytest.mark.integration
class TestChapterScribeRetrieval:
    @pytest.mark.asyncio
    async def test_scribe_receives_source_chunks_when_indexed(
        self, async_session: AsyncSession
    ) -> None:
        """Chapter scribe prompt contains 'Relevant source material:' when chunks exist."""
        topic_id = uuid.uuid4()
        ephemeral = chromadb.EphemeralClient()
        source_id = uuid.uuid4()

        # Pre-populate ChromaDB with known content
        upsert_source_chunks(
            ephemeral,
            topic_id,
            source_id,
            ["Neural networks learn from data through backpropagation."],
        )

        captured_prompts: list[str] = []

        async def _fake_run_agent(instruction: str, prompt: str) -> str:
            captured_prompts.append(prompt)
            return "Generated chapter content."

        with (
            patch(
                "documentlm_core.agents.chapter_scribe.get_chroma_client",
                return_value=ephemeral,
            ),
            patch(
                "documentlm_core.agents.chapter_scribe._run_agent",
                new=AsyncMock(side_effect=_fake_run_agent),
            ),
            patch(
                "documentlm_core.services.chapter.get_context_summaries",
                new=AsyncMock(return_value=[]),
            ),
        ):
            from documentlm_core.agents.chapter_scribe import run_chapter_scribe

            await run_chapter_scribe(
                item_id=uuid.uuid4(),
                item_title="Neural Networks",
                item_description="Introduction to neural network training",
                topic_id=topic_id,
                session=async_session,
            )

        assert len(captured_prompts) == 1
        assert "Relevant source material:" in captured_prompts[0]
        assert "backpropagation" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_scribe_proceeds_without_chunks(
        self, async_session: AsyncSession
    ) -> None:
        """Chapter scribe generates normally when ChromaDB has no chunks for the topic."""
        topic_id = uuid.uuid4()
        ephemeral = chromadb.EphemeralClient()  # empty — no chunks

        captured_prompts: list[str] = []

        async def _fake_run_agent(instruction: str, prompt: str) -> str:
            captured_prompts.append(prompt)
            return "Generated chapter content."

        with (
            patch(
                "documentlm_core.agents.chapter_scribe.get_chroma_client",
                return_value=ephemeral,
            ),
            patch(
                "documentlm_core.agents.chapter_scribe._run_agent",
                new=AsyncMock(side_effect=_fake_run_agent),
            ),
            patch(
                "documentlm_core.services.chapter.get_context_summaries",
                new=AsyncMock(return_value=[]),
            ),
        ):
            from documentlm_core.agents.chapter_scribe import run_chapter_scribe

            result = await run_chapter_scribe(
                item_id=uuid.uuid4(),
                item_title="Databases",
                item_description=None,
                topic_id=topic_id,
                session=async_session,
            )

        assert result == "Generated chapter content."
        assert "Relevant source material:" not in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_scribe_context_bounded_to_ten_chunks(
        self, async_session: AsyncSession
    ) -> None:
        """Scribe receives at most 10 chunks regardless of collection size."""
        topic_id = uuid.uuid4()
        ephemeral = chromadb.EphemeralClient()
        source_id = uuid.uuid4()

        # Insert 15 chunks
        chunks = [f"Content chunk number {i} about neural networks." for i in range(15)]
        upsert_source_chunks(ephemeral, topic_id, source_id, chunks)

        captured_prompts: list[str] = []

        async def _fake_run_agent(instruction: str, prompt: str) -> str:
            captured_prompts.append(prompt)
            return "Done."

        with (
            patch(
                "documentlm_core.agents.chapter_scribe.get_chroma_client",
                return_value=ephemeral,
            ),
            patch(
                "documentlm_core.agents.chapter_scribe._run_agent",
                new=AsyncMock(side_effect=_fake_run_agent),
            ),
            patch(
                "documentlm_core.services.chapter.get_context_summaries",
                new=AsyncMock(return_value=[]),
            ),
        ):
            from documentlm_core.agents.chapter_scribe import run_chapter_scribe

            await run_chapter_scribe(
                item_id=uuid.uuid4(),
                item_title="Neural Networks",
                item_description=None,
                topic_id=topic_id,
                session=async_session,
            )

        prompt = captured_prompts[0]
        # Count separator occurrences — 10 chunks means 9 separators
        separator_count = prompt.count("\n\n---\n\n")
        assert separator_count <= 9  # at most 10 chunks
