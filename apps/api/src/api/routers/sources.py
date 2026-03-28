"""Sources router: source queue management and Academic Scout discovery."""

from __future__ import annotations

import logging
import os as _os
import uuid

from documentlm_core.db.session import get_session
from documentlm_core.services.source import list_sources, reject_source, verify_source
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter()

_templates_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_templates_dir)


@router.get("/topics/{topic_id}/sources", response_class=HTMLResponse)
async def get_sources(
    request: Request,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    sources = await list_sources(session, topic_id)
    return templates.TemplateResponse(
        request, "sources/queue.html", {"sources": sources, "topic_id": topic_id}
    )


@router.post("/topics/{topic_id}/sources/discover", response_class=HTMLResponse)
async def discover_sources(
    request: Request,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.topic import get_topic

    topic = await get_topic(session, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    import asyncio

    asyncio.create_task(_scout_bg(topic_id, topic.title))

    return templates.TemplateResponse(
        request, "sources/_row.html", {"pending": True, "topic_id": topic_id}
    )


@router.patch("/sources/{source_id}/verify", response_class=HTMLResponse)
async def patch_verify(
    request: Request,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        source = await verify_source(session, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return templates.TemplateResponse(request, "sources/_row.html", {"source": source})


@router.patch("/sources/{source_id}/reject", response_class=HTMLResponse)
async def patch_reject(
    request: Request,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        source = await reject_source(session, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return templates.TemplateResponse(request, "sources/_row.html", {"source": source})


async def _scout_bg(topic_id: uuid.UUID, topic_title: str) -> None:
    from documentlm_core.agents.academic_scout import run_academic_scout
    from documentlm_core.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        try:
            await run_academic_scout(topic_id, topic_title, session)
            await session.commit()
        except Exception:
            logger.exception("Academic Scout failed for topic_id=%s", topic_id)
            await session.rollback()
