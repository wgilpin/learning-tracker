"""Bibliography router: verified sources for a topic."""

from __future__ import annotations

import logging
import uuid

from api.templates_config import templates
from documentlm_core.db.session import get_session
from documentlm_core.dependencies import get_current_user_id
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/topics/{topic_id}/bibliography", response_class=HTMLResponse)
async def get_bibliography(
    request: Request,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    from documentlm_core.services.bibliography import get_bibliography
    from documentlm_core.services.topic import get_topic

    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    entries = await get_bibliography(session, topic_id)
    return templates.TemplateResponse(
        request, "topics/_bibliography.html", {"entries": entries, "topic_id": topic_id}
    )
