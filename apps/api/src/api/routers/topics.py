"""Topics router: GET /, POST /topics, GET /topics/{id}, GET /topics/{id}/status."""

from __future__ import annotations

import asyncio
import logging
import uuid

from documentlm_core.db.session import get_session
from documentlm_core.dependencies import get_current_user_id
from documentlm_core.schemas import TopicCreate
from documentlm_core.services.source import list_sources
from documentlm_core.services.syllabus import list_syllabus_items, list_top_level_items
from documentlm_core.services.topic import create_topic, delete_topic, get_topic, get_topic_by_slug, list_topics, update_topic_level
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter()

_extending_topics: set[uuid.UUID] = set()


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
    level: str = Form(default="intermediate"),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    if not title or not title.strip():
        raise HTTPException(status_code=422, detail="title is required")

    topic = await create_topic(
        session, TopicCreate(title=title.strip(), description=description, level=level), user_id=user_id
    )
    await session.commit()

    logger.info("Created topic topic_id=%s — redirecting to source intake", topic.id)
    return RedirectResponse(url=f"/topics/{topic.id}/sources", status_code=303)


@router.delete("/topics/{topic_slug}", response_class=HTMLResponse)
async def delete_topic_endpoint(
    topic_slug: str,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    topic = await get_topic_by_slug(session, topic_slug, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    deleted = await delete_topic(session, topic.id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Topic not found")
    await session.commit()
    logger.info("Deleted topic slug=%s id=%s", topic_slug, topic.id)
    return Response(status_code=200, headers={"HX-Trigger": "topicDeleted"})


@router.get("/topics/_new_form", response_class=HTMLResponse)
async def new_topic_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "topics/_new_form.html", {})


@router.get("/topics/{topic_slug}", response_class=HTMLResponse)
async def get_topic_detail(
    request: Request,
    topic_slug: str,
    lesson: str | None = None,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    from documentlm_core.db.models import SyllabusItem as _SI
    from sqlalchemy import select

    topic = await get_topic_by_slug(session, topic_slug, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    lesson_id: uuid.UUID | None = None
    if lesson:
        result = await session.execute(
            select(_SI.id).where(_SI.slug == lesson, _SI.topic_id == topic.id)
        )
        lesson_id = result.scalar_one_or_none()

    return templates.TemplateResponse(
        request,
        "topics/detail.html",
        {"topic": topic, "lesson_id": lesson_id},
    )


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
    level: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    """Kick off syllabus generation using primary sources as context."""
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    # If the user changed the level on the intake page, persist it
    if level and level != topic.level:
        await update_topic_level(session, topic_id, level, user_id=user_id)
        await session.commit()

    effective_level = level or topic.level or "intermediate"

    primary_sources = await list_sources(session, topic_id, primary_only=True)
    primary_texts = [s.content for s in primary_sources if s.content]

    background_tasks.add_task(_run_syllabus_architect, topic_id, topic.title, primary_texts, effective_level)
    background_tasks.add_task(_run_academic_scout, topic_id, topic.title)

    logger.info(
        "Queued generation for topic_id=%s primary_sources=%d", topic_id, len(primary_sources)
    )
    return RedirectResponse(url=f"/topics/{topic.slug}", status_code=303)


async def _run_syllabus_architect(
    topic_id: uuid.UUID,
    topic_title: str,
    primary_source_texts: list[str] | None = None,
    level: str = "intermediate",
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
            await run_syllabus_architect(topic_id, topic_title, tools, primary_source_texts, level)
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


async def _run_syllabus_extender(
    topic_id: uuid.UUID,
    topic_title: str,
    extension_prompt: str,
    existing_section_titles: list[str],
    level: str = "intermediate",
) -> None:
    """Background task: run Syllabus Extender and persist new items."""
    from documentlm_core.agents.syllabus_architect import run_syllabus_extender
    from documentlm_core.db.session import AsyncSessionFactory
    from documentlm_core.schemas import SyllabusItemCreate

    class _DBTools:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session

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
            return item.id

    async with AsyncSessionFactory() as session:
        tools = _DBTools(session)
        try:
            await run_syllabus_extender(
                topic_id, topic_title, extension_prompt, existing_section_titles, tools, level
            )
            await session.commit()
            logger.info("Syllabus extension complete for topic_id=%s", topic_id)
        except Exception:
            logger.exception("Syllabus extension failed for topic_id=%s", topic_id)
            await session.rollback()
        finally:
            _extending_topics.discard(topic_id)


@router.post("/topics/{topic_id}/syllabus/extend")
async def post_extend_syllabus(
    topic_id: uuid.UUID,
    extension_prompt: str = Form(...),
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    """Start a background syllabus extension task."""
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if topic_id in _extending_topics:
        return JSONResponse({"error": "already in progress"}, status_code=409)

    existing = await list_top_level_items(session, topic_id)
    existing_titles = [item.title for item in existing]

    _extending_topics.add(topic_id)
    asyncio.create_task(
        _run_syllabus_extender(
            topic_id, topic.title, extension_prompt.strip(), existing_titles, topic.level or "intermediate"
        )
    )

    logger.info("Queued syllabus extension for topic_id=%s prompt=%r", topic_id, extension_prompt)
    return JSONResponse({"status": "started"})


@router.get("/topics/{topic_id}/extend-status")
async def get_extend_status(
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    """Return the current extension status for a topic."""
    topic = await get_topic(session, topic_id, user_id=user_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    status = "pending" if topic_id in _extending_topics else "complete"
    return JSONResponse({"status": status})
