"""Chapters router — stub, fully implemented in Phase 4 (US2) and Phase 6 (US4)."""

from __future__ import annotations

import logging
import uuid

from documentlm_core.db.session import get_session
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter()

# Guards against duplicate background drafts when polling fires before the first draft completes.
_drafting_items: set[uuid.UUID] = set()
_failed_items: set[uuid.UUID] = set()
# Tracks chapters whose illustration pipeline is still running.
_illustrating_chapters: set[uuid.UUID] = set()


@router.get("/syllabus-items/{item_id}/chapter", response_class=HTMLResponse)
async def get_or_trigger_chapter(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.db.models import AtomicChapter, SyllabusItem
    from documentlm_core.services.chapter import get_chapter
    from sqlalchemy import select

    item = (
        await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="SyllabusItem not found")

    existing = (await session.execute(
        select(AtomicChapter).where(AtomicChapter.syllabus_item_id == item_id)
    )).scalar_one_or_none()

    if existing is not None:
        from documentlm_core.config import settings
        from documentlm_core.services.illustration import get_illustrations
        chapter = await get_chapter(session, existing.id)
        has_quiz = existing.quiz_questions is not None
        illustrations = await get_illustrations(session, existing.id)
        return templates.TemplateResponse(
            request,
            "chapters/_inline.html",
            {
                "chapter": chapter,
                "item": item,
                "has_quiz": has_quiz,
                "illustrations": illustrations,
                "illustrations_pending": existing.id in _illustrating_chapters,
                "dev_mode": bool(settings.dev_password),
                "cost_input_per_m": settings.cost_input_per_m,
                "cost_output_per_m": settings.cost_output_per_m,
                "cost_per_image": settings.cost_per_image,
            },
        )

    if item_id in _failed_items:
        return templates.TemplateResponse(request, "chapters/_failed.html", {"item_id": item_id})

    if item_id not in _drafting_items:
        import asyncio
        _drafting_items.add(item_id)
        asyncio.create_task(_draft_chapter_bg(item_id, item.topic_id, item.title, item.description))
    return templates.TemplateResponse(request, "chapters/_generating.html", {"item_id": item_id})


@router.post("/syllabus-items/{item_id}/chapter", response_class=HTMLResponse)
async def post_chapter_draft(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Request a chapter draft for a SyllabusItem whose parent already has a chapter."""
    from documentlm_core.db.models import AtomicChapter, SyllabusItem
    from sqlalchemy import select

    result = await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="SyllabusItem not found")

    if item.parent_id is not None:
        parent_ch = await session.execute(
            select(AtomicChapter).where(AtomicChapter.syllabus_item_id == item.parent_id)
        )
        if parent_ch.scalar_one_or_none() is None:
            raise HTTPException(status_code=409, detail="Parent chapter not yet drafted")

    from documentlm_core.db.models import AtomicChapter
    from sqlalchemy import select as _s2

    existing = await session.execute(
        _s2(AtomicChapter).where(AtomicChapter.syllabus_item_id == item_id)
    )
    chapter = existing.scalar_one_or_none()

    if chapter is None and item_id not in _drafting_items:
        import asyncio

        _drafting_items.add(item_id)
        asyncio.create_task(_draft_chapter_bg(item_id, item.topic_id, item.title, item.description))

    return templates.TemplateResponse(
        request, "chapters/_status_card.html", {"item_id": item_id, "chapter": chapter}
    )


@router.delete("/syllabus-items/{item_id}/chapter", response_class=HTMLResponse)
async def regenerate_chapter(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Dev-mode only: delete the current chapter and trigger a fresh draft.

    Only available when DEV_PASSWORD is configured in the environment.
    """
    from documentlm_core.config import settings

    if not settings.dev_password:
        raise HTTPException(status_code=403, detail="Only available in dev mode")

    from documentlm_core.db.models import AtomicChapter, SyllabusItem
    from sqlalchemy import select

    item = (
        await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="SyllabusItem not found")

    existing = (
        await session.execute(
            select(AtomicChapter).where(AtomicChapter.syllabus_item_id == item_id)
        )
    ).scalar_one_or_none()

    if existing is not None:
        await session.delete(existing)
        await session.commit()

    _failed_items.discard(item_id)
    _drafting_items.discard(item_id)

    import asyncio

    _drafting_items.add(item_id)
    asyncio.create_task(
        _draft_chapter_bg(item_id, item.topic_id, item.title, item.description)
    )
    logger.info("Chapter regeneration triggered for item_id=%s", item_id)
    return templates.TemplateResponse(
        request, "chapters/_generating.html", {"item_id": item_id}
    )


@router.get("/chapters/{chapter_id}", response_class=HTMLResponse)
async def get_chapter(
    request: Request,
    chapter_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.chapter import get_chapter as _get_chapter
    from documentlm_core.services.illustration import get_illustrations

    chapter = await _get_chapter(session, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    illustrations = await get_illustrations(session, chapter_id)
    from documentlm_core.config import settings as _settings
    return templates.TemplateResponse(
        request,
        "chapters/detail.html",
        {
            "chapter": chapter,
            "illustrations": illustrations,
            "cost_input_per_m": _settings.cost_input_per_m,
            "cost_output_per_m": _settings.cost_output_per_m,
            "cost_per_image": _settings.cost_per_image,
        },
    )


@router.get("/chapters/{chapter_id}/illustrations/{paragraph_index}")
async def get_chapter_illustration(
    chapter_id: uuid.UUID,
    paragraph_index: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.db.models import ChapterIllustration
    from sqlalchemy import select

    result = await session.execute(
        select(ChapterIllustration).where(
            ChapterIllustration.chapter_id == chapter_id,
            ChapterIllustration.paragraph_index == paragraph_index,
        )
    )
    illustration = result.scalar_one_or_none()
    if illustration is None:
        raise HTTPException(status_code=404, detail="Illustration not found")

    logger.info(
        "Illustration served chapter_id=%s paragraph=%d bytes=%d",
        chapter_id,
        paragraph_index,
        len(illustration.image_data),
    )
    return Response(
        content=illustration.image_data,
        media_type=illustration.image_mime_type,
    )


@router.get("/chapters/{chapter_id}/status")
async def chapter_status(
    chapter_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    from documentlm_core.db.models import AtomicChapter
    from sqlalchemy import select

    result = await session.execute(select(AtomicChapter).where(AtomicChapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        return JSONResponse({"status": "pending"})
    return JSONResponse({"status": "complete"})


@router.post("/chapters/{chapter_id}/comments", response_class=HTMLResponse)
async def post_comment(
    request: Request,
    chapter_id: uuid.UUID,
    paragraph_anchor: str = Form(...),
    selected_text: str | None = Form(None),
    content: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    import asyncio

    from documentlm_core.schemas import MarginCommentCreate
    from documentlm_core.services.margin_comment import create_comment

    try:
        comment = await create_comment(
            session,
            chapter_id,
            MarginCommentCreate(
                paragraph_anchor=paragraph_anchor,
                selected_text=selected_text,
                content=content,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Commit before launching background task so the new session can see the row
    await session.commit()
    asyncio.create_task(_respond_to_comment_bg(comment.id, chapter_id))

    response = templates.TemplateResponse(
        request, "chapters/_margin_comment.html", {"comment": comment}
    )
    response.headers["HX-Retarget"] = f"#comments-{paragraph_anchor}"
    response.headers["HX-Reswap"] = "beforeend"
    return response


@router.get("/comments/{comment_id}", response_class=HTMLResponse)
async def get_comment(
    request: Request,
    comment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from datetime import UTC, datetime, timedelta

    from documentlm_core.db.models import MarginComment
    from sqlalchemy import select

    result = await session.execute(select(MarginComment).where(MarginComment.id == comment_id))
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    timed_out = (
        comment.response is None
        and datetime.now(UTC) - comment.created_at > timedelta(minutes=5)
    )
    return templates.TemplateResponse(
        request, "chapters/_margin_comment.html", {"comment": comment, "timed_out": timed_out}
    )


@router.delete("/comments/{comment_id}", response_class=HTMLResponse)
async def delete_comment(
    comment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.db.models import MarginComment
    from sqlalchemy import select

    result = await session.execute(select(MarginComment).where(MarginComment.id == comment_id))
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    await session.delete(comment)
    return HTMLResponse("")


@router.patch("/comments/{comment_id}/resolve", response_class=HTMLResponse)
async def resolve_comment(
    request: Request,
    comment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.db.models import MarginComment as _MC
    from documentlm_core.db.models import SyllabusItem
    from documentlm_core.services.chapter import get_chapter
    from documentlm_core.services.margin_comment import resolve_and_apply
    from sqlalchemy import select
    from sqlalchemy import select as _sel

    comment_row = (
        await session.execute(_sel(_MC).where(_MC.id == comment_id))
    ).scalar_one_or_none()
    if comment_row is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    if not comment_row.response:
        # No response to apply — just delete the comment and return empty
        await session.delete(comment_row)
        await session.commit()
        return HTMLResponse("")

    try:
        chapter_id = await resolve_and_apply(session, comment_id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    from documentlm_core.config import settings
    from documentlm_core.services.illustration import get_illustrations

    chapter = await get_chapter(session, chapter_id)
    item = (await session.execute(
        select(SyllabusItem).where(SyllabusItem.id == chapter.syllabus_item_id)
    )).scalar_one()
    illustrations = await get_illustrations(session, chapter_id)

    response = templates.TemplateResponse(
        request,
        "chapters/_inline.html",
        {
            "chapter": chapter,
            "item": item,
            "illustrations": illustrations,
            "illustrations_pending": chapter.id in _illustrating_chapters,
            "dev_mode": bool(settings.dev_password),
        },
    )
    response.headers["HX-Retarget"] = "#reading-panel"
    response.headers["HX-Reswap"] = "innerHTML"
    return response


async def _draft_chapter_bg(
    item_id: uuid.UUID,
    topic_id: uuid.UUID,
    item_title: str,
    item_description: str | None = None,
) -> None:
    from documentlm_core.agents.chapter_scribe import run_chapter_scribe
    from documentlm_core.db.models import AtomicChapter as _AC
    from documentlm_core.db.session import AsyncSessionFactory
    from documentlm_core.schemas import TokenUsage
    from documentlm_core.services.chapter import create_chapter
    from documentlm_core.services.illustration import run_illustration_pipeline
    from sqlalchemy import update as _upd

    try:
        async with AsyncSessionFactory() as session:
            try:
                from documentlm_core.db.models import SyllabusItem
                from sqlalchemy import select as _sel_si

                item_row = (
                    await session.execute(_sel_si(SyllabusItem).where(SyllabusItem.id == item_id))
                ).scalar_one_or_none()
                objectives = item_row.learning_objectives if item_row else None

                draft = await run_chapter_scribe(
                    item_id,
                    item_title,
                    topic_id,
                    session,
                    item_description=item_description,
                    learning_objectives=objectives,
                )
                chapter = await create_chapter(
                    session,
                    item_id,
                    topic_id,
                    draft.content,
                    draft.cited_source_ids,
                    input_tokens=draft.token_usage.input_tokens,
                    output_tokens=draft.token_usage.output_tokens,
                )
                await session.commit()
                logger.info(
                    "Chapter drafted for item_id=%s citations=%d",
                    item_id,
                    len(draft.cited_source_ids),
                )
            except Exception:
                logger.exception("Chapter drafting failed for item_id=%s", item_id)
                await session.rollback()
                _failed_items.add(item_id)
                return

        # Run illustration pipeline in a fresh session after chapter is committed.
        # Failures here must never affect chapter availability.
        _illustrating_chapters.add(chapter.id)
        image_count = 0
        assess_usage = TokenUsage()
        async with AsyncSessionFactory() as ill_session:
            try:
                image_count, assess_usage = await run_illustration_pipeline(
                    chapter.id, draft.content, ill_session
                )
                await ill_session.commit()
            except Exception:
                logger.exception(
                    "Illustration pipeline failed for chapter_id=%s item_id=%s",
                    chapter.id,
                    item_id,
                )
                await ill_session.rollback()
            finally:
                _illustrating_chapters.discard(chapter.id)

        # Update chapter with final token totals (scribe + assessor) and image count.
        async with AsyncSessionFactory() as update_session:
            try:
                total_input = draft.token_usage.input_tokens + assess_usage.input_tokens
                total_output = draft.token_usage.output_tokens + assess_usage.output_tokens
                await update_session.execute(
                    _upd(_AC)
                    .where(_AC.id == chapter.id)
                    .values(
                        generation_input_tokens=total_input,
                        generation_output_tokens=total_output,
                        generation_image_count=image_count,
                    )
                )
                await update_session.commit()
            except Exception:
                logger.exception(
                    "Token usage update failed for chapter_id=%s", chapter.id
                )
                await update_session.rollback()
    finally:
        _drafting_items.discard(item_id)


async def _respond_to_comment_bg(comment_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
    from documentlm_core.agents.chapter_scribe import respond_to_comment
    from documentlm_core.db.session import AsyncSessionFactory
    from documentlm_core.services.margin_comment import attach_response

    async with AsyncSessionFactory() as session:
        try:
            response_text = await respond_to_comment(comment_id, chapter_id, session)
            await attach_response(session, comment_id, response_text)
            await session.commit()
        except Exception:
            logger.exception("Comment response failed for comment_id=%s", comment_id)
            await session.rollback()
