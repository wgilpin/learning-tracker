"""Bibliography router: verified sources for a topic."""

from __future__ import annotations

import logging
import os as _os
import uuid

from documentlm_core.db.session import get_session
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter()

_templates_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_templates_dir)


@router.get("/topics/{topic_id}/bibliography", response_class=HTMLResponse)
async def get_bibliography(
    request: Request,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.bibliography import get_bibliography

    entries = await get_bibliography(session, topic_id)
    return templates.TemplateResponse(
        request, "topics/_bibliography.html", {"entries": entries, "topic_id": topic_id}
    )
