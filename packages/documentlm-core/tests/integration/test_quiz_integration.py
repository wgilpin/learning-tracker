"""Integration tests for quiz service against real Postgres."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from documentlm_core.db.models import AtomicChapter, SyllabusItem, Topic, User
from documentlm_core.schemas import QuizQuestion, QuizState
from sqlalchemy.ext.asyncio import AsyncSession


def _make_questions() -> list[QuizQuestion]:
    return [
        QuizQuestion(text=f"Q{i}?", options=["A", "B", "C"], correct_index=0, explanation="A.")
        for i in range(3)
    ]


async def _make_chapter(session: AsyncSession) -> AtomicChapter:
    import bcrypt

    user = User(
        id=uuid.uuid4(),
        email=f"quiztest-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=4)).decode(),
    )
    session.add(user)
    await session.flush()

    topic = Topic(title="Quiz Topic", user_id=user.id)
    session.add(topic)
    await session.flush()

    item = SyllabusItem(topic_id=topic.id, title="Chapter")
    session.add(item)
    await session.flush()

    chapter = AtomicChapter(
        topic_id=topic.id,
        syllabus_item_id=item.id,
        content="Content about machine learning.",
    )
    session.add(chapter)
    await session.flush()
    return chapter


class TestGetOrCreateQuiz:
    @pytest.mark.asyncio
    async def test_get_or_create_quiz_creates_once(
        self, async_session: AsyncSession
    ) -> None:
        from documentlm_core.services.quiz import get_or_create_quiz

        chapter = await _make_chapter(async_session)

        mock_questions = _make_questions()
        with patch(
            "documentlm_core.services.quiz.generate_quiz_questions",
            new=AsyncMock(return_value=mock_questions),
        ):
            state1 = await get_or_create_quiz(async_session, chapter.id)
            state2 = await get_or_create_quiz(async_session, chapter.id)

        assert len(state1.questions) == len(mock_questions)
        assert len(state2.questions) == len(mock_questions)
        # Questions should be identical (generated only once)
        assert state1.questions[0].text == state2.questions[0].text

    @pytest.mark.asyncio
    async def test_submit_response_updates_db(
        self, async_session: AsyncSession
    ) -> None:
        from documentlm_core.services.quiz import get_or_create_quiz, submit_response

        chapter = await _make_chapter(async_session)
        mock_questions = _make_questions()

        with patch(
            "documentlm_core.services.quiz.generate_quiz_questions",
            new=AsyncMock(return_value=mock_questions),
        ):
            await get_or_create_quiz(async_session, chapter.id)

        await submit_response(async_session, chapter.id, 0, 0)
        await async_session.refresh(chapter)

        assert chapter.quiz_user_responses is not None
        assert chapter.quiz_user_responses[0] == 0

    @pytest.mark.asyncio
    async def test_quiz_passed_set_on_final_answer(
        self, async_session: AsyncSession
    ) -> None:
        from documentlm_core.services.quiz import get_or_create_quiz, submit_response

        chapter = await _make_chapter(async_session)
        mock_questions = _make_questions()  # all correct_index=0

        with patch(
            "documentlm_core.services.quiz.generate_quiz_questions",
            new=AsyncMock(return_value=mock_questions),
        ):
            await get_or_create_quiz(async_session, chapter.id)

        # Submit all correct answers
        for i in range(len(mock_questions)):
            result = await submit_response(async_session, chapter.id, i, 0)

        await async_session.refresh(chapter)
        assert chapter.quiz_passed is True

    @pytest.mark.asyncio
    async def test_quiz_not_passed_below_threshold(
        self, async_session: AsyncSession
    ) -> None:
        from documentlm_core.services.quiz import get_or_create_quiz, submit_response

        chapter = await _make_chapter(async_session)
        mock_questions = _make_questions()  # correct_index=0

        with patch(
            "documentlm_core.services.quiz.generate_quiz_questions",
            new=AsyncMock(return_value=mock_questions),
        ):
            await get_or_create_quiz(async_session, chapter.id)

        # Submit all wrong answers
        for i in range(len(mock_questions)):
            await submit_response(async_session, chapter.id, i, 2)  # wrong

        await async_session.refresh(chapter)
        assert chapter.quiz_passed is False

    @pytest.mark.asyncio
    async def test_reset_quiz_clears_responses_keeps_questions(
        self, async_session: AsyncSession
    ) -> None:
        from documentlm_core.services.quiz import (
            get_or_create_quiz,
            reset_quiz,
            submit_response,
        )

        chapter = await _make_chapter(async_session)
        mock_questions = _make_questions()

        with patch(
            "documentlm_core.services.quiz.generate_quiz_questions",
            new=AsyncMock(return_value=mock_questions),
        ):
            await get_or_create_quiz(async_session, chapter.id)

        # Answer all
        for i in range(len(mock_questions)):
            await submit_response(async_session, chapter.id, i, 0)

        await reset_quiz(async_session, chapter.id)
        await async_session.refresh(chapter)

        assert chapter.quiz_questions is not None
        assert len(chapter.quiz_questions) == len(mock_questions)
        assert chapter.quiz_user_responses is not None
        assert all(r is None for r in chapter.quiz_user_responses)
        assert chapter.quiz_passed is None
