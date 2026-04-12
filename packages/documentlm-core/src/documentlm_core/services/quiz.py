"""Quiz service: generate, persist, score, and reset chapter quizzes."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.schemas import QuizAnswerResult, QuizQuestion, QuizState

logger = logging.getLogger(__name__)

QUIZ_PASSING_THRESHOLD: float = 0.80


def score_quiz(questions: list[QuizQuestion], responses: list[int | None]) -> float:
    """Return fraction of correctly-answered questions. None responses count as wrong."""
    if not questions:
        return 0.0
    correct = sum(
        1
        for q, r in zip(questions, responses, strict=False)
        if r is not None and r == q.correct_index
    )
    return correct / len(questions)


async def generate_quiz_questions(
    chapter_content: str,
    n: int = 5,
    learning_objectives: list[dict] | None = None,
) -> list[QuizQuestion]:
    """Call ADK agent to generate n multiple-choice questions from chapter content.

    If learning_objectives are provided, questions are aligned to the Bloom's level
    of each objective so that each one is directly testable.
    """
    from documentlm_core.agents.chat_agent import _run_agent

    if learning_objectives:
        obj_lines = "\n".join(
            f"- [{o.get('bloom_level', 'understand')}] {o.get('text', '')}"
            for o in learning_objectives
        )
        objectives_block = (
            f"\nLearning objectives for this chapter (align questions to these, "
            f"matching their Bloom's cognitive level):\n{obj_lines}\n"
        )
    else:
        objectives_block = ""

    instruction = (
        "You are a quiz generator. Given a chapter excerpt, produce exactly "
        f"{n} multiple-choice questions that test understanding of the key ideas.\n"
        f"{objectives_block}\n"
        "Output ONLY a JSON array with this exact structure — no prose, no markdown fences:\n"
        '[\n'
        '  {\n'
        '    "text": "Question text?",\n'
        '    "options": ["Option A", "Option B", "Option C"],\n'
        '    "correct_index": 0,\n'
        '    "explanation": "Why this answer is correct."\n'
        '  }\n'
        ']\n\n'
        "Rules:\n"
        "- Exactly 3–4 options per question.\n"
        "- correct_index is 0-based.\n"
        "- All questions must be answerable from the provided content.\n"
        "- Output only the JSON array, nothing else."
    )

    prompt = f"Chapter content:\n\n{chapter_content[:4000]}\n\nGenerate {n} quiz questions."
    logger.info("generate_quiz_questions: calling LLM for %d questions", n)

    raw = await _run_agent(instruction, prompt)
    logger.debug("generate_quiz_questions: raw response length=%d", len(raw))

    # Strip possible markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # drop first and last line if they are fences
        inner = [line for line in lines if not line.startswith("```")]
        cleaned = "\n".join(inner).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.exception("generate_quiz_questions: failed to parse JSON response: %r", raw[:200])
        raise RuntimeError("Quiz generation returned invalid JSON") from None

    questions = [QuizQuestion(**item) for item in data]
    logger.info("generate_quiz_questions: generated %d questions", len(questions))
    return questions


async def get_or_create_quiz(
    session: AsyncSession,
    chapter_id: uuid.UUID,
) -> QuizState:
    """Return existing quiz state or generate a new one (idempotent)."""
    from documentlm_core.db.models import AtomicChapter

    result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ValueError(f"Chapter {chapter_id} not found")

    if chapter.quiz_questions is not None:
        logger.debug("get_or_create_quiz: returning existing quiz for chapter_id=%s", chapter_id)
        questions = [QuizQuestion(**q) for q in chapter.quiz_questions]
        return QuizState(
            questions=questions,
            user_responses=chapter.quiz_user_responses or [None] * len(questions),
            passed=chapter.quiz_passed,
            generated_at=chapter.quiz_generated_at or datetime.now(UTC),
        )

    logger.info("get_or_create_quiz: generating new quiz for chapter_id=%s", chapter_id)
    from documentlm_core.db.models import SyllabusItem
    item_result = await session.execute(
        select(SyllabusItem).where(SyllabusItem.id == chapter.syllabus_item_id)
    )
    item = item_result.scalar_one_or_none()
    objectives = item.learning_objectives if item else None
    questions = await generate_quiz_questions(chapter.content, learning_objectives=objectives)
    now = datetime.now(UTC)

    chapter.quiz_questions = [q.model_dump() for q in questions]
    chapter.quiz_user_responses = [None] * len(questions)
    chapter.quiz_passed = None
    chapter.quiz_generated_at = now
    await session.flush()
    logger.info(
        "get_or_create_quiz: persisted %d questions for chapter_id=%s",
        len(questions),
        chapter_id,
    )

    return QuizState(
        questions=questions,
        user_responses=[None] * len(questions),
        passed=None,
        generated_at=now,
    )


async def submit_response(
    session: AsyncSession,
    chapter_id: uuid.UUID,
    question_index: int,
    selected_index: int,
) -> QuizAnswerResult:
    """Record an answer for one question. Score and set quiz_passed on completion."""
    from documentlm_core.db.models import AtomicChapter

    result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ValueError(f"Chapter {chapter_id} not found")

    questions_data = chapter.quiz_questions
    if not questions_data:
        raise ValueError(f"Chapter {chapter_id} has no quiz questions")

    questions = [QuizQuestion(**q) for q in questions_data]

    if question_index < 0 or question_index >= len(questions):
        raise IndexError(
            f"question_index {question_index} out of range for {len(questions)} questions"
        )

    responses: list[int | None] = list(chapter.quiz_user_responses or [None] * len(questions))
    responses[question_index] = selected_index
    chapter.quiz_user_responses = responses

    is_correct = selected_index == questions[question_index].correct_index
    explanation = questions[question_index].explanation

    quiz_passed: bool | None = None
    if all(r is not None for r in responses):
        final_score = score_quiz(questions, responses)
        quiz_passed = final_score >= QUIZ_PASSING_THRESHOLD
        chapter.quiz_passed = quiz_passed
        logger.info(
            "submit_response: quiz complete for chapter_id=%s score=%.2f passed=%s",
            chapter_id,
            final_score,
            quiz_passed,
        )

    await session.flush()

    return QuizAnswerResult(
        question_index=question_index,
        is_correct=is_correct,
        explanation=explanation,
        quiz_passed=quiz_passed,
    )


async def reset_quiz(session: AsyncSession, chapter_id: uuid.UUID) -> None:
    """Clear user responses and pass state. Questions remain unchanged."""
    from documentlm_core.db.models import AtomicChapter

    result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise ValueError(f"Chapter {chapter_id} not found")

    n = len(chapter.quiz_questions or [])
    chapter.quiz_user_responses = [None] * n
    chapter.quiz_passed = None
    await session.flush()
    logger.info("reset_quiz: cleared responses for chapter_id=%s (%d questions)", chapter_id, n)
