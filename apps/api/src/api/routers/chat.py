"""Chat router: SSE streaming and quiz CRUD endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from documentlm_core.db.session import get_session
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.routers.topics import _extending_topics
from api.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


async def _verify_topic_ownership(
    topic_id: uuid.UUID,
    session: AsyncSession,
    request: Request,
) -> None:
    from documentlm_core.db.models import Topic

    user_id_str = request.session.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = uuid.UUID(user_id_str)

    result = await session.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if topic is None or topic.user_id != user_id:
        raise HTTPException(status_code=404, detail="Topic not found")


async def _verify_chapter_ownership(
    chapter_id: uuid.UUID,
    session: AsyncSession,
    request: Request,
) -> None:
    from documentlm_core.db.models import AtomicChapter, Topic

    user_id_str = request.session.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = uuid.UUID(user_id_str)

    result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    topic_result = await session.execute(
        select(Topic).where(Topic.id == chapter.topic_id)
    )
    topic = topic_result.scalar_one_or_none()
    if topic is None or topic.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chapter not found")


async def _sse_stream(chunks: AsyncIterator[str]) -> AsyncIterator[str]:
    async for chunk in chunks:
        data = json.dumps({"chunk": chunk, "done": False})
        yield f"data: {data}\n\n"
    data = json.dumps({"chunk": "", "done": True})
    yield f"data: {data}\n\n"


# ---------------------------------------------------------------------------
# POST /topics/{topic_id}/chat/stream
# ---------------------------------------------------------------------------


@router.post("/topics/{topic_id}/chat/stream")
async def chat_stream(
    request: Request,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.agents.chat_agent import (
        classify_intent,
        stream_expand_response,
        stream_qa_response,
        stream_socratic_response,
    )
    from documentlm_core.schemas import ChatRequest

    await _verify_topic_ownership(topic_id, session, request)

    body = await request.json()
    chat_request = ChatRequest.model_validate(body)
    messages = chat_request.messages
    chapter_id = chat_request.chapter_id

    if not messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")

    latest_user_message = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )

    async def _generate() -> AsyncIterator[str]:
        # Yield a keepalive comment immediately so the client clears its timeout
        # while intent classification (which can take 10–15 s) runs server-side.
        yield ": ping\n\n"

        try:
            intent = await classify_intent(latest_user_message)
        except Exception:
            logger.exception("chat_stream: intent classification failed")
            intent = "qa"

        logger.info(
            "chat_stream: topic_id=%s intent=%s chapter_id=%s", topic_id, intent, chapter_id
        )

        if intent == "quiz" and chapter_id is not None:
            data = json.dumps({"quiz_redirect": f"/chapters/{chapter_id}/quiz", "done": True})
            yield f"data: {data}\n\n"
            return

        if intent == "extend_syllabus":
            if topic_id in _extending_topics:
                msg = "I'm already extending the syllabus. Please wait for it to finish."
                yield f"data: {json.dumps({'chunk': msg, 'done': False})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return
            msg = f'I can extend the syllabus based on: "{latest_user_message}". Shall I proceed?'
            yield f"data: {json.dumps({'chunk': msg, 'done': False})}\n\n"
            yield f"data: {json.dumps({'syllabus_extend_confirm': True, 'extension_prompt': latest_user_message, 'done': True})}\n\n"
            return

        try:
            if intent == "socratic":
                chunks = stream_socratic_response(messages, topic_id, session)
            elif intent == "expand":
                chunks = stream_expand_response(messages, topic_id, session)
            else:
                chunks = stream_qa_response(messages, topic_id, session)

            async for sse_chunk in _sse_stream(chunks):
                yield sse_chunk
        except Exception:
            logger.exception("chat_stream: agent streaming failed for topic_id=%s", topic_id)
            yield f"data: {json.dumps({'chunk': 'Sorry, something went wrong. Please try again.', 'done': False})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /chapters/{chapter_id}/quiz
# ---------------------------------------------------------------------------


@router.get("/chapters/{chapter_id}/quiz", response_class=HTMLResponse)
async def get_quiz(
    request: Request,
    chapter_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.quiz import get_or_create_quiz

    await _verify_chapter_ownership(chapter_id, session, request)

    try:
        quiz_state = await get_or_create_quiz(session, chapter_id)
    except RuntimeError as exc:
        logger.exception("get_quiz: quiz generation failed for chapter_id=%s", chapter_id)
        raise HTTPException(status_code=503, detail="Quiz generation failed") from exc

    return templates.TemplateResponse(
        request,
        "chat/_quiz.html",
        {"quiz": quiz_state, "chapter_id": chapter_id},
    )


# ---------------------------------------------------------------------------
# POST /chapters/{chapter_id}/quiz/responses
# ---------------------------------------------------------------------------


@router.post("/chapters/{chapter_id}/quiz/responses", response_class=HTMLResponse)
async def post_quiz_response(
    request: Request,
    chapter_id: uuid.UUID,
    question_index: int = Form(...),
    selected_option_index: int = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.quiz import get_or_create_quiz, submit_response

    await _verify_chapter_ownership(chapter_id, session, request)

    try:
        result = await submit_response(session, chapter_id, question_index, selected_option_index)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    quiz_state = await get_or_create_quiz(session, chapter_id)

    response = templates.TemplateResponse(
        request,
        "chat/_quiz_question.html",
        {
            "question": quiz_state.questions[question_index],
            "question_index": question_index,
            "user_response": result.question_index,
            "is_correct": result.is_correct,
            "answered": True,
            "chapter_id": chapter_id,
        },
    )

    if result.quiz_passed is not None:
        response.headers["HX-Trigger"] = "quizComplete"
        if result.quiz_passed:
            from documentlm_core.db.models import AtomicChapter
            from documentlm_core.services.syllabus import mark_all_objectives_mastered
            from sqlalchemy import select as _sel

            chapter_row = (
                await session.execute(_sel(AtomicChapter).where(AtomicChapter.id == chapter_id))
            ).scalar_one_or_none()
            if chapter_row is not None:
                await mark_all_objectives_mastered(session, chapter_row.syllabus_item_id)
                await session.commit()

    return response


# ---------------------------------------------------------------------------
# GET /chapters/{chapter_id}/quiz/result
# ---------------------------------------------------------------------------


@router.get("/chapters/{chapter_id}/quiz/result", response_class=HTMLResponse)
async def get_quiz_result(
    request: Request,
    chapter_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.db.models import AtomicChapter

    await _verify_chapter_ownership(chapter_id, session, request)

    result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if chapter.quiz_passed is None:
        raise HTTPException(status_code=422, detail="Quiz not yet completed")

    total = len(chapter.quiz_questions or [])
    correct = sum(
        1
        for i, q in enumerate(chapter.quiz_questions or [])
        if (chapter.quiz_user_responses or [])[i] == q["correct_index"]
    )

    return templates.TemplateResponse(
        request,
        "chat/_quiz_result.html",
        {
            "passed": chapter.quiz_passed,
            "correct": correct,
            "total": total,
            "chapter_id": chapter_id,
        },
    )


# ---------------------------------------------------------------------------
# POST /chapters/{chapter_id}/quiz/retake
# ---------------------------------------------------------------------------


@router.post("/chapters/{chapter_id}/quiz/retake", response_class=HTMLResponse)
async def retake_quiz(
    request: Request,
    chapter_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.quiz import get_or_create_quiz, reset_quiz

    await _verify_chapter_ownership(chapter_id, session, request)

    await reset_quiz(session, chapter_id)
    quiz_state = await get_or_create_quiz(session, chapter_id)

    return templates.TemplateResponse(
        request,
        "chat/_quiz.html",
        {"quiz": quiz_state, "chapter_id": chapter_id},
    )
