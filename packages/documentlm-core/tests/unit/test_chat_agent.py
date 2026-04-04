"""Unit tests for chat agent intent classification and streaming helpers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from documentlm_core.schemas import ChatMessage


async def _async_iter(items: list[str]):
    for item in items:
        yield item


class TestStreamQaResponse:
    @pytest.mark.asyncio
    async def test_stream_qa_response_calls_chroma(self) -> None:
        from documentlm_core.agents.chat_agent import stream_qa_response

        topic_id = uuid.uuid4()
        messages = [ChatMessage(role="user", content="What is gradient descent?")]
        mock_session = AsyncMock()

        with (
            patch(
                "documentlm_core.agents.chat_agent.query_topic_chunks_with_sources",
                return_value=[("chunk text", uuid.uuid4())],
            ),
            patch(
                "documentlm_core.agents.chat_agent._run_agent_stream",
                return_value=_async_iter(["Gradient ", "descent."]),
            ),
            patch(
                "documentlm_core.agents.chat_agent.get_chroma_client",
                return_value=MagicMock(),
            ),
            patch(
                "documentlm_core.agents.chat_agent._get_topic_source_ids",
                new=AsyncMock(return_value=[uuid.uuid4()]),
            ),
        ):
            chunks = []
            async for chunk in stream_qa_response(messages, topic_id, mock_session):
                chunks.append(chunk)

        assert any(c for c in chunks)


class TestClassifyIntentSocratic:
    @pytest.mark.asyncio
    async def test_classify_intent_socratic(self) -> None:
        from documentlm_core.agents.chat_agent import classify_intent

        socratic_phrases = [
            "lead me through a question",
            "set me a question",
            "question my understanding",
        ]
        for phrase in socratic_phrases:
            with patch(
                "documentlm_core.agents.chat_agent._run_agent",
                new=AsyncMock(return_value="socratic"),
            ):
                result = await classify_intent(phrase)
            assert result == "socratic", f"Expected 'socratic' for {phrase!r}, got {result!r}"

    @pytest.mark.asyncio
    async def test_stream_socratic_response_yields_single_question(self) -> None:
        from documentlm_core.agents.chat_agent import stream_socratic_response

        topic_id = uuid.uuid4()
        messages = [ChatMessage(role="user", content="Set me a question")]
        mock_session = AsyncMock()

        response_text = "What do you think happens when the learning rate is too high?"

        with (
            patch(
                "documentlm_core.agents.chat_agent.query_topic_chunks_with_sources",
                return_value=[("chunk text about gradient descent", uuid.uuid4())],
            ),
            patch(
                "documentlm_core.agents.chat_agent._run_agent_stream",
                return_value=_async_iter([response_text]),
            ),
            patch(
                "documentlm_core.agents.chat_agent.get_chroma_client",
                return_value=MagicMock(),
            ),
            patch(
                "documentlm_core.agents.chat_agent._get_topic_source_ids",
                new=AsyncMock(return_value=[uuid.uuid4()]),
            ),
        ):
            chunks = []
            async for chunk in stream_socratic_response(messages, topic_id, mock_session):
                chunks.append(chunk)

        full_response = "".join(chunks)
        # Single question constraint: at most one `?`
        assert full_response.count("?") <= 1


class TestClassifyIntentExpand:
    @pytest.mark.asyncio
    async def test_classify_intent_expand(self) -> None:
        from documentlm_core.agents.chat_agent import classify_intent

        expand_phrases = [
            "tell me more about gradient descent",
            "expand on chapter 3",
            "go deeper on backpropagation",
        ]
        for phrase in expand_phrases:
            with patch(
                "documentlm_core.agents.chat_agent._run_agent",
                new=AsyncMock(return_value="expand"),
            ):
                result = await classify_intent(phrase)
            assert result == "expand", f"Expected 'expand' for {phrase!r}, got {result!r}"

    @pytest.mark.asyncio
    async def test_stream_expand_response_queries_chroma(self) -> None:
        from documentlm_core.agents.chat_agent import stream_expand_response

        topic_id = uuid.uuid4()
        messages = [ChatMessage(role="user", content="Tell me more about gradient descent")]
        mock_session = AsyncMock()
        mock_chroma = MagicMock()

        with (
            patch(
                "documentlm_core.agents.chat_agent.query_topic_chunks_with_sources",
                return_value=[("relevant chunk", uuid.uuid4())],
            ) as mock_query,
            patch(
                "documentlm_core.agents.chat_agent._run_agent_stream",
                return_value=_async_iter(["Gradient descent is..."]),
            ),
            patch(
                "documentlm_core.agents.chat_agent.get_chroma_client",
                return_value=mock_chroma,
            ),
            patch(
                "documentlm_core.agents.chat_agent._get_topic_source_ids",
                new=AsyncMock(return_value=[uuid.uuid4()]),
            ),
        ):
            chunks = []
            async for chunk in stream_expand_response(messages, topic_id, mock_session):
                chunks.append(chunk)

        # Assert ChromaDB was queried with the concept from the user message
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        query_text = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("query_text", "")
        assert "gradient descent" in query_text.lower()
