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
    query_topic_chunks_with_sources,
    upsert_source_chunks,
)
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
class TestPipelineEndToEnd:
    @pytest.mark.asyncio
    async def test_search_source_indexed_after_pipeline(
        self, async_session: AsyncSession, test_user
    ) -> None:
        """A SEARCH source with a URL is INDEXED after extract_and_index_source runs."""
        from documentlm_core.db.models import Source, Topic
        from documentlm_core.services.pipeline import extract_and_index_source

        topic = Topic(title="Test Topic", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        source = Source(
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

        chunks = query_topic_chunks_with_sources(
            ephemeral, [source.id], "machine learning", n_results=10
        )
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_failed_extraction_does_not_block_other_sources(
        self, async_session: AsyncSession, test_user
    ) -> None:
        """A source that fails extraction is marked FAILED; pipeline does not raise."""
        from documentlm_core.db.models import Source, Topic
        from documentlm_core.services.pipeline import extract_and_index_source

        topic = Topic(title="Test Topic 2", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        source = Source(
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
        self, async_session: AsyncSession, test_user
    ) -> None:
        """A SEARCH source with only a DOI (no URL) is marked FAILED immediately."""
        from documentlm_core.db.models import Source, Topic
        from documentlm_core.services.pipeline import extract_and_index_source

        topic = Topic(title="DOI Topic", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        source = Source(
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
        self, async_session: AsyncSession, test_user
    ) -> None:
        """Chapter scribe prompt contains source material when chunks exist."""
        from documentlm_core.db.models import Source, Topic, UserSourceRef

        topic = Topic(title="ML Topic", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        source = Source(
            title="Backpropagation Paper",
            authors=["LeCun"],
            source_type="SEARCH",
        )
        async_session.add(source)
        await async_session.flush()

        # Add UserSourceRef so chapter scribe can find this source for the topic
        ref = UserSourceRef(
            user_id=test_user.id,
            source_id=source.id,
            topic_id=topic.id,
        )
        async_session.add(ref)
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()

        # Pre-populate ChromaDB with known content linked to this source
        upsert_source_chunks(
            ephemeral,
            source.id,
            ["Neural networks learn from data through backpropagation."],
        )

        captured_prompts: list[str] = []

        async def _fake_run_agent(instruction: str, prompt: str):
            from documentlm_core.schemas import TokenUsage
            captured_prompts.append(prompt)
            return "Generated chapter content.", TokenUsage()

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
                "documentlm_core.agents.chapter_scribe._chunks_cover_topic",
                new=AsyncMock(return_value=True),
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
                topic_id=topic.id,
                session=async_session,
            )

        assert len(captured_prompts) == 1
        assert "Available sources" in captured_prompts[0]
        assert "backpropagation" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_scribe_proceeds_without_chunks(
        self, async_session: AsyncSession
    ) -> None:
        """Chapter scribe generates normally when ChromaDB has no chunks for the topic."""
        topic_id = uuid.uuid4()
        ephemeral = chromadb.EphemeralClient()  # empty — no chunks

        captured_prompts: list[str] = []

        async def _fake_run_agent(instruction: str, prompt: str):
            from documentlm_core.schemas import TokenUsage
            captured_prompts.append(prompt)
            return "Generated chapter content.", TokenUsage()

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

        assert result.content == "Generated chapter content."
        assert "Available sources" not in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_scribe_context_bounded_to_ten_chunks(
        self, async_session: AsyncSession, test_user
    ) -> None:
        """Scribe receives at most 10 chunks regardless of collection size."""
        from documentlm_core.db.models import Source, Topic, UserSourceRef

        topic = Topic(title="Chunks Topic", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        source = Source(title="Big Source", authors=[], source_type="SEARCH")
        async_session.add(source)
        await async_session.flush()

        ref = UserSourceRef(
            user_id=test_user.id,
            source_id=source.id,
            topic_id=topic.id,
        )
        async_session.add(ref)
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()

        # Insert 15 chunks
        chunks = [f"Content chunk number {i} about neural networks." for i in range(15)]
        upsert_source_chunks(ephemeral, source.id, chunks)

        captured_prompts: list[str] = []

        async def _fake_run_agent(instruction: str, prompt: str):
            from documentlm_core.schemas import TokenUsage
            captured_prompts.append(prompt)
            return "Done.", TokenUsage()

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
                "documentlm_core.agents.chapter_scribe._chunks_cover_topic",
                new=AsyncMock(return_value=True),
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
                topic_id=topic.id,
                session=async_session,
            )

        prompt = captured_prompts[0]
        # Count separator occurrences — 10 chunks means 9 separators
        separator_count = prompt.count("\n\n---\n\n")
        assert separator_count <= 9  # at most 10 chunks

    @pytest.mark.asyncio
    async def test_scribe_triggers_academic_scout_when_no_chunks(
        self, async_session: AsyncSession, test_user
    ) -> None:
        """When ChromaDB returns no chunks, Academic Scout is triggered to find sources."""
        from documentlm_core.db.models import Topic

        topic = Topic(title="Knowledge Graphs", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()  # empty — no chunks

        async def _fake_run_agent(instruction: str, prompt: str):
            from documentlm_core.schemas import TokenUsage
            return "Chapter content.", TokenUsage()

        scout_calls: list[tuple] = []

        async def _fake_scout_requery(topic_id, item_title, query_text, session, chroma_client):
            scout_calls.append((topic_id, query_text))
            return []  # no new sources found

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
            patch(
                "documentlm_core.agents.chapter_scribe._scout_and_requery",
                new=AsyncMock(side_effect=_fake_scout_requery),
            ),
        ):
            from documentlm_core.agents.chapter_scribe import run_chapter_scribe

            await run_chapter_scribe(
                item_id=uuid.uuid4(),
                item_title="Knowledge Graph Embeddings",
                item_description="TransR and RotatE models",
                topic_id=topic.id,
                session=async_session,
            )

        assert len(scout_calls) == 1
        assert scout_calls[0][0] == topic.id

    @pytest.mark.asyncio
    async def test_scribe_does_not_trigger_scout_when_chunks_relevant(
        self, async_session: AsyncSession, test_user
    ) -> None:
        """When chunks exist and LLM judges them relevant, Academic Scout is NOT triggered."""
        from documentlm_core.db.models import Source, Topic, UserSourceRef

        topic = Topic(title="ML Topic", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        source = Source(title="Embeddings Paper", authors=[], source_type="SEARCH")
        async_session.add(source)
        await async_session.flush()
        async_session.add(UserSourceRef(
            user_id=test_user.id, source_id=source.id, topic_id=topic.id
        ))
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()
        upsert_source_chunks(
            ephemeral,
            source.id,
            ["TransE embeds entities into a continuous vector space."],
        )

        scout_called = False

        async def _fake_scout(*args, **kwargs):
            nonlocal scout_called
            scout_called = True
            return []

        async def _fake_run_agent(instruction: str, prompt: str):
            from documentlm_core.schemas import TokenUsage
            return "Chapter content.", TokenUsage()

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
                "documentlm_core.agents.chapter_scribe._chunks_cover_topic",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "documentlm_core.services.chapter.get_context_summaries",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "documentlm_core.agents.chapter_scribe._scout_and_requery",
                new=AsyncMock(side_effect=_fake_scout),
            ),
        ):
            from documentlm_core.agents.chapter_scribe import run_chapter_scribe

            await run_chapter_scribe(
                item_id=uuid.uuid4(),
                item_title="Knowledge Graph Embeddings",
                item_description="TransR and RotatE models",
                topic_id=topic.id,
                session=async_session,
            )

        assert not scout_called

    @pytest.mark.asyncio
    async def test_scribe_triggers_scout_when_chunks_irrelevant(
        self, async_session: AsyncSession, test_user
    ) -> None:
        """When chunks exist but LLM judges them off-topic, Academic Scout IS triggered."""
        from documentlm_core.db.models import Source, Topic, UserSourceRef

        topic = Topic(title="Knowledge Graphs", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        source = Source(title="Intro to Graphs", authors=[], source_type="SEARCH")
        async_session.add(source)
        await async_session.flush()
        async_session.add(UserSourceRef(
            user_id=test_user.id, source_id=source.id, topic_id=topic.id
        ))
        await async_session.flush()

        ephemeral = chromadb.EphemeralClient()
        upsert_source_chunks(
            ephemeral,
            source.id,
            ["A graph is a set of vertices connected by edges."],
        )

        scout_calls: list[tuple] = []

        async def _fake_scout_requery(topic_id, item_title, query_text, session, chroma_client):
            scout_calls.append((topic_id, query_text))
            return []

        async def _fake_run_agent(instruction: str, prompt: str):
            from documentlm_core.schemas import TokenUsage
            return "Chapter content.", TokenUsage()

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
                "documentlm_core.agents.chapter_scribe._chunks_cover_topic",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "documentlm_core.services.chapter.get_context_summaries",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "documentlm_core.agents.chapter_scribe._scout_and_requery",
                new=AsyncMock(side_effect=_fake_scout_requery),
            ),
        ):
            from documentlm_core.agents.chapter_scribe import run_chapter_scribe

            await run_chapter_scribe(
                item_id=uuid.uuid4(),
                item_title="Knowledge Graph Embeddings",
                item_description="TransR and RotatE models",
                topic_id=topic.id,
                session=async_session,
            )

        assert len(scout_calls) == 1
        assert scout_calls[0][0] == topic.id
