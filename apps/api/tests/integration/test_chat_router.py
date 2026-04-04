"""Integration tests for chat and quiz HTTP endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from documentlm_core.db.models import AtomicChapter, SyllabusItem, Topic


async def _async_iter(items: list[str]):
    for item in items:
        yield item


class TestChatStreamQa:
    @pytest.mark.asyncio
    async def test_chat_stream_qa_returns_sse(
        self, test_client, async_session, test_user
    ) -> None:
        # Create topic + syllabus item + chapter so ownership check passes
        topic = Topic(title="Test Topic", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        with (
            patch(
                "documentlm_core.agents.chat_agent.classify_intent",
                new=AsyncMock(return_value="qa"),
            ),
            patch(
                "documentlm_core.agents.chat_agent.stream_qa_response",
                return_value=_async_iter(["Hello ", "world."]),
            ),
        ):
            response = await test_client.post(
                f"/topics/{topic.id}/chat/stream",
                json={
                    "messages": [{"role": "user", "content": "What is this?"}],
                    "chapter_id": None,
                },
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "data:" in body
        assert '"done": false' in body


class TestGetQuiz:
    @pytest.mark.asyncio
    async def test_get_quiz_returns_html(
        self, test_client, async_session, test_user
    ) -> None:
        topic = Topic(title="Quiz Topic", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        item = SyllabusItem(topic_id=topic.id, title="Chapter 1")
        async_session.add(item)
        await async_session.flush()

        chapter = AtomicChapter(
            topic_id=topic.id,
            syllabus_item_id=item.id,
            content="Some chapter content.",
        )
        async_session.add(chapter)
        await async_session.flush()

        with patch(
            "documentlm_core.services.quiz.get_or_create_quiz",
            new=AsyncMock(
                return_value=MagicMock(
                    questions=[
                        MagicMock(
                            text="Q1?",
                            options=["A", "B", "C"],
                            correct_index=0,
                            explanation="Because A.",
                        )
                    ],
                    user_responses=[None],
                    passed=None,
                    generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                )
            ),
        ):
            response = await test_client.get(f"/chapters/{chapter.id}/quiz")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_post_quiz_response_returns_feedback(
        self, test_client, async_session, test_user
    ) -> None:
        from documentlm_core.schemas import QuizAnswerResult

        topic = Topic(title="Quiz Topic 2", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        item = SyllabusItem(topic_id=topic.id, title="Chapter 2")
        async_session.add(item)
        await async_session.flush()

        chapter = AtomicChapter(
            topic_id=topic.id,
            syllabus_item_id=item.id,
            content="Chapter content.",
        )
        async_session.add(chapter)
        await async_session.flush()

        result = QuizAnswerResult(
            question_index=0,
            is_correct=True,
            explanation="Because A.",
            quiz_passed=None,
        )

        with patch(
            "documentlm_core.services.quiz.submit_response",
            new=AsyncMock(return_value=result),
        ):
            response = await test_client.post(
                f"/chapters/{chapter.id}/quiz/responses",
                data={"question_index": "0", "selected_option_index": "0"},
            )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_get_quiz_result_after_completion(
        self, test_client, async_session, test_user
    ) -> None:
        topic = Topic(title="Quiz Topic 3", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        item = SyllabusItem(topic_id=topic.id, title="Chapter 3")
        async_session.add(item)
        await async_session.flush()

        chapter = AtomicChapter(
            topic_id=topic.id,
            syllabus_item_id=item.id,
            content="Content.",
            quiz_passed=True,
            quiz_questions=[{"text": "Q?", "options": ["A"], "correct_index": 0, "explanation": "A"}],
            quiz_user_responses=[0],
        )
        async_session.add(chapter)
        await async_session.flush()

        response = await test_client.get(f"/chapters/{chapter.id}/quiz/result")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_retake_quiz_clears_responses(
        self, test_client, async_session, test_user
    ) -> None:
        topic = Topic(title="Quiz Topic 4", user_id=test_user.id)
        async_session.add(topic)
        await async_session.flush()

        item = SyllabusItem(topic_id=topic.id, title="Chapter 4")
        async_session.add(item)
        await async_session.flush()

        chapter = AtomicChapter(
            topic_id=topic.id,
            syllabus_item_id=item.id,
            content="Content.",
            quiz_passed=False,
            quiz_questions=[{"text": "Q?", "options": ["A", "B"], "correct_index": 0, "explanation": "A"}],
            quiz_user_responses=[1],
        )
        async_session.add(chapter)
        await async_session.flush()

        with patch(
            "documentlm_core.services.quiz.get_or_create_quiz",
            new=AsyncMock(
                return_value=MagicMock(
                    questions=[
                        MagicMock(
                            text="Q?",
                            options=["A", "B"],
                            correct_index=0,
                            explanation="A",
                        )
                    ],
                    user_responses=[None],
                    passed=None,
                    generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                )
            ),
        ):
            response = await test_client.post(f"/chapters/{chapter.id}/quiz/retake")

        assert response.status_code == 200
        # Responses should be cleared in DB
        await async_session.refresh(chapter)
        assert chapter.quiz_passed is None
