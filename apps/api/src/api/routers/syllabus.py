"""Syllabus router: CRUD endpoints for syllabus items."""

from __future__ import annotations

import logging
import uuid

from documentlm_core.db.models import AtomicChapter
from documentlm_core.db.session import get_session
from documentlm_core.dependencies import get_current_user_id
from documentlm_core.schemas import (
    SyllabusItemCreate,
    SyllabusItemRead,
    SyllabusItemStatusUpdate,
    SyllabusItemUpdate,
    SyllabusStatus,
)
from documentlm_core.services.syllabus import (
    create_syllabus_item,
    delete_syllabus_item,
    generate_item_description,
    get_ancestor_ids,
    has_associated_content,
    has_duplicate_title,
    list_children,
    list_top_level_items,
    update_status,
    update_syllabus_item,
)
from documentlm_core.services.topic import get_topic
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/topics/{topic_id}/syllabus", response_class=HTMLResponse)
async def get_syllabus(
    request: Request,
    topic_id: uuid.UUID,
    lesson: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    items = await list_top_level_items(session, topic_id)
    ancestor_ids: set[uuid.UUID] = set(await get_ancestor_ids(session, lesson)) if lesson else set()
    return templates.TemplateResponse(
        request,
        "topics/_syllabus_panel.html",
        {
            "items": items,
            "topic_id": topic_id,
            "topic_slug": topic.slug,
            "lesson_id": lesson,
            "ancestor_ids": ancestor_ids,
        },
    )


@router.get("/syllabus-items/{item_id}/children", response_class=HTMLResponse)
async def get_children(
    request: Request,
    item_id: uuid.UUID,
    lesson: uuid.UUID | None = None,
    topic_slug: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> Response:
    children = await list_children(session, item_id)
    leaf_ids: list[uuid.UUID] = []
    is_leaf_map: dict[uuid.UUID, bool] = {}
    for child in children:
        grandchildren = await list_children(session, child.id)
        is_leaf = len(grandchildren) == 0
        is_leaf_map[child.id] = is_leaf
        if is_leaf:
            leaf_ids.append(child.id)

    items_with_chapters: set[uuid.UUID] = set()
    quiz_passed_map: dict[uuid.UUID, bool | None] = {}
    if leaf_ids:
        result = await session.execute(
            select(
                AtomicChapter.syllabus_item_id,
                AtomicChapter.quiz_passed,
            ).where(AtomicChapter.syllabus_item_id.in_(leaf_ids))
        )
        for row in result:
            items_with_chapters.add(row[0])
            quiz_passed_map[row[0]] = row[1]

    ancestor_ids: set[uuid.UUID] = set(await get_ancestor_ids(session, lesson)) if lesson else set()
    children_with_flags: list[tuple] = [
        (child, is_leaf_map[child.id], child.id in items_with_chapters)
        for child in children
    ]
    return templates.TemplateResponse(
        request,
        "syllabus/_children_list.html",
        {
            "children_with_flags": children_with_flags,
            "lesson_id": lesson,
            "topic_slug": topic_slug,
            "ancestor_ids": ancestor_ids,
            "quiz_passed_map": quiz_passed_map,
        },
    )


@router.patch("/syllabus-items/{item_id}/status", response_class=HTMLResponse)
async def patch_status(
    request: Request,
    item_id: uuid.UUID,
    status: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        status_enum = SyllabusStatus(status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}") from None

    try:
        item = await update_status(session, item_id, SyllabusItemStatusUpdate(status=status_enum))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = await session.execute(
        select(AtomicChapter.syllabus_item_id).where(AtomicChapter.syllabus_item_id == item_id)
    )
    has_chapter = result.scalar_one_or_none() is not None
    topic = await get_topic(session, item.topic_id)
    return templates.TemplateResponse(
        request,
        "syllabus/_child_item.html",
        {"child": item, "is_leaf": True, "has_chapter": has_chapter, "topic_slug": topic.slug if topic else None},
    )


@router.post("/topics/{topic_id}/syllabus-items", response_class=HTMLResponse)
async def post_syllabus_item(
    request: Request,
    topic_id: uuid.UUID,
    title: str = Form(...),
    description: str = Form(""),
    parent_id: uuid.UUID | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    stripped_title = title.strip()
    if not stripped_title:
        return templates.TemplateResponse(
            request,
            "syllabus/_add_item_form.html",
            {"topic_id": topic_id, "parent_id": parent_id, "error": "Title must not be empty."},
            status_code=422,
        )

    item = await create_syllabus_item(
        session,
        SyllabusItemCreate(
            topic_id=topic_id,
            title=stripped_title,
            description=description or None,
            parent_id=parent_id,
        ),
    )

    is_dup = await has_duplicate_title(
        session, topic_id, parent_id, stripped_title, exclude_id=item.id
    )

    result = await session.execute(
        select(AtomicChapter.syllabus_item_id).where(AtomicChapter.syllabus_item_id == item.id)
    )
    has_chapter = result.scalar_one_or_none() is not None

    return templates.TemplateResponse(
        request,
        "syllabus/_child_item.html",
        {
            "child": item,
            "is_leaf": True,
            "has_chapter": has_chapter,
            "duplicate_warning": is_dup,
            "lesson_id": None,
            "ancestor_ids": set(),
            "topic_slug": topic.slug if topic else None,
        },
    )


@router.get("/topics/{topic_id}/syllabus-items/add-form", response_class=HTMLResponse)
async def get_add_item_form(
    request: Request,
    topic_id: uuid.UUID,
    parent_id: uuid.UUID | None = None,
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    return templates.TemplateResponse(
        request,
        "syllabus/_add_item_form.html",
        {"topic_id": topic_id, "parent_id": parent_id},
    )


@router.post("/topics/{topic_id}/syllabus-items/generate-description", response_class=HTMLResponse)
async def post_generate_description_for_new_item(
    request: Request,
    topic_id: uuid.UUID,
    title: str = Form(...),
    parent_id: uuid.UUID | None = Form(None),
    session: AsyncSession = Depends(get_session),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    stripped = title.strip()
    if not stripped:
        return templates.TemplateResponse(
            request,
            "syllabus/_description_error.html",
            {"error": "Title must not be empty."},
            status_code=422,
        )

    try:
        description = await generate_item_description(session, topic_id, parent_id, stripped)
    except RuntimeError:
        logger.exception("generate-description failed for topic_id=%s", topic_id)
        return templates.TemplateResponse(
            request,
            "syllabus/_description_error.html",
            {"error": "Description generation failed. Please try again."},
            status_code=503,
        )

    return templates.TemplateResponse(
        request,
        "syllabus/_description_textarea.html",
        {"description": description},
    )


@router.post("/syllabus-items/{item_id}/generate-description", response_class=HTMLResponse)
async def post_generate_description(
    request: Request,
    item_id: uuid.UUID,
    title: str = Form(...),
    session: AsyncSession = Depends(get_session),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    from documentlm_core.db.models import SyllabusItem as _SI

    stripped = title.strip()
    if not stripped:
        return templates.TemplateResponse(
            request,
            "syllabus/_description_error.html",
            {"error": "Title must not be empty."},
            status_code=422,
        )

    item_result = await session.execute(select(_SI).where(_SI.id == item_id))
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        description = await generate_item_description(
            session, item.topic_id, item.parent_id, stripped
        )
    except RuntimeError:
        logger.exception("generate-description failed for item_id=%s", item_id)
        return templates.TemplateResponse(
            request,
            "syllabus/_description_error.html",
            {"error": "Description generation failed. Please try again."},
            status_code=503,
        )

    return templates.TemplateResponse(
        request,
        "syllabus/_description_textarea.html",
        {"description": description},
    )


@router.patch("/syllabus-items/{item_id}", response_class=HTMLResponse)
async def patch_syllabus_item(
    request: Request,
    item_id: uuid.UUID,
    title: str | None = Form(None),
    description: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    try:
        item = await update_syllabus_item(
            session, item_id, SyllabusItemUpdate(title=title, description=description)
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        return templates.TemplateResponse(
            request,
            "syllabus/_edit_item_form.html",
            {
                "item_id": item_id,
                "title": title or "",
                "description": description or "",
                "error": msg,
            },
            status_code=422,
        )

    is_dup = await has_duplicate_title(
        session, item.topic_id, item.parent_id, item.title, exclude_id=item.id
    )

    result = await session.execute(
        select(AtomicChapter.syllabus_item_id).where(AtomicChapter.syllabus_item_id == item_id)
    )
    has_chapter = result.scalar_one_or_none() is not None
    topic = await get_topic(session, item.topic_id)

    return templates.TemplateResponse(
        request,
        "syllabus/_child_item.html",
        {
            "child": item,
            "is_leaf": True,
            "has_chapter": has_chapter,
            "duplicate_warning": is_dup,
            "lesson_id": None,
            "ancestor_ids": set(),
            "topic_slug": topic.slug if topic else None,
        },
    )


@router.get("/syllabus-items/{item_id}/edit-form", response_class=HTMLResponse)
async def get_edit_item_form(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    from documentlm_core.db.models import SyllabusItem as _SI

    item_result = await session.execute(select(_SI).where(_SI.id == item_id))
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return templates.TemplateResponse(
        request,
        "syllabus/_edit_item_form.html",
        {"item_id": item_id, "title": item.title, "description": item.description or ""},
    )


@router.get("/syllabus-items/{item_id}/restore", response_class=HTMLResponse)
async def restore_item_row(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    from documentlm_core.db.models import SyllabusItem as _SI

    item_result = await session.execute(select(_SI).where(_SI.id == item_id))
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    chapter_result = await session.execute(
        select(AtomicChapter.syllabus_item_id).where(AtomicChapter.syllabus_item_id == item_id)
    )
    has_chapter = chapter_result.scalar_one_or_none() is not None
    item_read = SyllabusItemRead.model_validate(item)
    topic = await get_topic(session, item.topic_id)

    return templates.TemplateResponse(
        request,
        "syllabus/_child_item.html",
        {
            "child": item_read,
            "is_leaf": True,
            "has_chapter": has_chapter,
            "duplicate_warning": False,
            "lesson_id": None,
            "ancestor_ids": set(),
            "topic_slug": topic.slug if topic else None,
        },
    )


@router.get("/syllabus-items/{item_id}/delete-confirm", response_class=HTMLResponse)
async def get_delete_confirm(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    from documentlm_core.db.models import SyllabusItem as _SI

    item_result = await session.execute(select(_SI).where(_SI.id == item_id))
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    has_content = await has_associated_content(session, item_id)

    count_result = await session.execute(
        select(_SI).where(_SI.topic_id == item.topic_id)
    )
    total_count = len(count_result.scalars().all())
    is_last = total_count == 1

    return templates.TemplateResponse(
        request,
        "syllabus/_delete_confirm.html",
        {"item_id": item_id, "has_content": has_content, "is_last": is_last},
    )


@router.delete("/syllabus-items/{item_id}", response_class=HTMLResponse)
async def delete_syllabus_item_route(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    try:
        await delete_syllabus_item(session, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(status_code=200)
