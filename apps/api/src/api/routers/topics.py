"""Topics router: GET /, POST /topics, GET /topics/{id}, GET /topics/{id}/status."""

from __future__ import annotations

import logging
import uuid

from documentlm_core.db.session import get_session
from documentlm_core.dependencies import get_current_user_id
from documentlm_core.schemas import TopicCreate
from documentlm_core.services.source import list_sources
from documentlm_core.services.syllabus import list_syllabus_items
from documentlm_core.services.topic import create_topic, delete_topic, get_topic, list_topics
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    from documentlm_core.config import settings

    topics = await list_topics(session, user_id=user_id)
    return templates.TemplateResponse(
        request, "topics/list.html", {"topics": topics, "debug": settings.debug}
    )


@router.post("/topics")
async def post_topic(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    if not title or not title.strip():
        raise HTTPException(status_code=422, detail="title is required")

    topic = await create_topic(
        session, TopicCreate(title=title.strip(), description=description), user_id=user_id
    )
    await session.commit()

    logger.info("Created topic topic_id=%s — redirecting to source intake", topic.id)
    return RedirectResponse(url=f"/topics/{topic.id}/sources", status_code=303)


@router.delete("/topics/{topic_id}", response_class=HTMLResponse)
async def delete_topic_endpoint(
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    deleted = await delete_topic(session, topic_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Topic not found")
    await session.commit()
    logger.info("Deleted topic topic_id=%s", topic_id)
    return Response(status_code=200, headers={"HX-Trigger": "topicDeleted"})


@router.get("/topics/_new_form", response_class=HTMLResponse)
async def new_topic_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "topics/_new_form.html", {})


@router.get("/topics/{topic_id}", response_class=HTMLResponse)
async def get_topic_detail(
    request: Request,
    topic_id: uuid.UUID,
    lesson: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return templates.TemplateResponse(request, "topics/detail.html", {"topic": topic, "lesson_id": lesson})


@router.get("/topics/{topic_id}/status")
async def topic_status(
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JSONResponse:
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    items = await list_syllabus_items(session, topic_id)
    status = "complete" if items else "pending"
    return JSONResponse({"status": status, "item_count": len(items)})


@router.post("/topics/{topic_id}/generate")
async def post_generate(
    background_tasks: BackgroundTasks,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    """Kick off syllabus generation using primary sources as context."""
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    primary_sources = await list_sources(session, topic_id, primary_only=True)
    primary_texts = [s.content for s in primary_sources if s.content]

    background_tasks.add_task(_run_syllabus_architect, topic_id, topic.title, primary_texts)
    background_tasks.add_task(_run_academic_scout, topic_id, topic.title)

    logger.info(
        "Queued generation for topic_id=%s primary_sources=%d", topic_id, len(primary_sources)
    )
    return RedirectResponse(url=f"/topics/{topic_id}", status_code=303)


async def _run_syllabus_architect(
    topic_id: uuid.UUID,
    topic_title: str,
    primary_source_texts: list[str] | None = None,
) -> None:
    """Background task: run Syllabus Architect and persist items."""
    from documentlm_core.agents.syllabus_architect import run_syllabus_architect
    from documentlm_core.db.session import AsyncSessionFactory
    from documentlm_core.schemas import SyllabusItemCreate

    class _DBTools:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session
            self._created: list[uuid.UUID] = []

        async def create_syllabus_item(
            self,
            topic_id: uuid.UUID,
            title: str,
            description: str | None,
            parent_id: uuid.UUID | None,
        ) -> uuid.UUID:
            from documentlm_core.services.syllabus import create_syllabus_item

            item = await create_syllabus_item(
                self._session,
                SyllabusItemCreate(
                    topic_id=topic_id,
                    title=title,
                    description=description,
                    parent_id=parent_id,
                ),
            )
            self._created.append(item.id)
            return item.id

    async with AsyncSessionFactory() as session:
        tools = _DBTools(session)
        try:
            await run_syllabus_architect(topic_id, topic_title, tools, primary_source_texts)
            await session.commit()
            logger.info("Syllabus generation complete for topic_id=%s", topic_id)
        except Exception:
            logger.exception("Syllabus generation failed for topic_id=%s", topic_id)
            await session.rollback()


async def _run_academic_scout(topic_id: uuid.UUID, topic_title: str) -> None:
    """Background task: run Academic Scout to discover supplemental sources."""
    from documentlm_core.agents.academic_scout import run_academic_scout
    from documentlm_core.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        try:
            await run_academic_scout(topic_id, topic_title, session)
            await session.commit()
        except Exception:
            logger.exception("Academic Scout failed for topic_id=%s", topic_id)
            await session.rollback()
