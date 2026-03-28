"""Syllabus router: GET /topics/{id}/syllabus, PATCH /syllabus-items/{id}/status."""

from __future__ import annotations

import logging
import uuid

from api.templates_config import templates
from documentlm_core.db.session import get_session
from documentlm_core.schemas import SyllabusItemStatusUpdate, SyllabusStatus
from documentlm_core.services.syllabus import list_children, list_top_level_items, update_status
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/topics/{topic_id}/syllabus", response_class=HTMLResponse)
async def get_syllabus(
    request: Request,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    items = await list_top_level_items(session, topic_id)
    return templates.TemplateResponse(
        request, "topics/_syllabus_panel.html", {"items": items, "topic_id": topic_id}
    )


@router.get("/syllabus-items/{item_id}/children", response_class=HTMLResponse)
async def get_children(
    request: Request,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    children = await list_children(session, item_id)
    children_with_flags: list[tuple] = []
    for child in children:
        grandchildren = await list_children(session, child.id)
        children_with_flags.append((child, len(grandchildren) == 0))
    return templates.TemplateResponse(
        request, "syllabus/_children_list.html", {"children_with_flags": children_with_flags}
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

    return templates.TemplateResponse(request, "syllabus/_child_item.html", {"child": item, "is_leaf": True})
