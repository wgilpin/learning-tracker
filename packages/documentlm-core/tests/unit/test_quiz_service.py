"""Unit tests for quiz service (no DB required)."""

from __future__ import annotations

import pytest
from documentlm_core.schemas import QuizQuestion


def _make_questions(n: int) -> list[QuizQuestion]:
    return [
        QuizQuestion(
            text=f"Q{i}?",
            options=["A", "B", "C"],
            correct_index=0,
            explanation="Because A.",
        )
        for i in range(n)
    ]


class TestScoreQuiz:
    def test_score_quiz_all_correct(self) -> None:
        from documentlm_core.services.quiz import score_quiz

        questions = _make_questions(3)
        responses = [0, 0, 0]
        assert score_quiz(questions, responses) == 1.0

    def test_score_quiz_all_wrong(self) -> None:
        from documentlm_core.services.quiz import score_quiz

        questions = _make_questions(3)
        responses = [1, 2, 1]
        assert score_quiz(questions, responses) == 0.0

    def test_score_quiz_partial(self) -> None:
        from documentlm_core.services.quiz import score_quiz

        questions = _make_questions(4)
        # 2 correct (index 0), 2 wrong
        responses = [0, 1, 0, 2]
        assert score_quiz(questions, responses) == 0.5

    def test_score_quiz_with_nulls(self) -> None:
        from documentlm_core.services.quiz import score_quiz

        questions = _make_questions(3)
        responses = [0, None, None]  # 1 correct, 2 unanswered (count as wrong)
        result = score_quiz(questions, responses)
        assert abs(result - 1 / 3) < 1e-9

    def test_score_quiz_empty(self) -> None:
        from documentlm_core.services.quiz import score_quiz

        assert score_quiz([], []) == 0.0
