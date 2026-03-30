"""Chapters router — stub, fully implemented in Phase 4 (US2) and Phase 6 (US4)."""

from __future__ import annotations

import logging
import uuid

from api.templates_config import templates
from documentlm_core.db.session import get_session
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter()

# Guards against duplicate background drafts when polling fires before the first draft completes.
_drafting_items: set[uuid.UUID] = set()
_failed_items: set[uuid.UUID] = set()


@router.get("/syllabus-items/{item_id}/chapter", response_class=HTMLResponse)
async def get_or_trigger_chapter(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.db.models import AtomicChapter, SyllabusItem
    from documentlm_core.services.chapter import get_chapter
    from sqlalchemy import select

    item = (await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="SyllabusItem not found")

    existing = (await session.execute(
        select(AtomicChapter).where(AtomicChapter.syllabus_item_id == item_id)
    )).scalar_one_or_none()

    if existing is not None:
        chapter = await get_chapter(session, existing.id)
        return templates.TemplateResponse(request, "chapters/_inline.html", {"chapter": chapter, "item": item})

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


@router.get("/chapters/{chapter_id}", response_class=HTMLResponse)
async def get_chapter(
    request: Request,
    chapter_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.chapter import get_chapter as _get_chapter

    chapter = await _get_chapter(session, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "chapters/detail.html", {"chapter": chapter})
    return templates.TemplateResponse(request, "chapters/detail.html", {"chapter": chapter})


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

    return templates.TemplateResponse(request, "chapters/_margin_comment.html", {"comment": comment})


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
    from documentlm_core.db.models import SyllabusItem
    from documentlm_core.services.chapter import get_chapter
    from documentlm_core.services.margin_comment import resolve_and_apply
    from sqlalchemy import select

    from documentlm_core.db.models import MarginComment as _MC
    from sqlalchemy import select as _sel

    comment_row = (await session.execute(_sel(_MC).where(_MC.id == comment_id))).scalar_one_or_none()
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

    chapter = await get_chapter(session, chapter_id)
    item = (await session.execute(
        select(SyllabusItem).where(SyllabusItem.id == chapter.syllabus_item_id)
    )).scalar_one()

    response = templates.TemplateResponse(
        request, "chapters/_inline.html", {"chapter": chapter, "item": item}
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
    from documentlm_core.db.session import AsyncSessionFactory
    from documentlm_core.services.chapter import create_chapter

    try:
        async with AsyncSessionFactory() as session:
            try:
                draft = await run_chapter_scribe(
                    item_id, item_title, topic_id, session, item_description=item_description
                )
                await create_chapter(session, item_id, topic_id, draft.content, draft.cited_source_ids)
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
