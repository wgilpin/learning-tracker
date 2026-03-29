"""Sources router: primary source intake and Academic Scout discovery."""

from __future__ import annotations

import logging
import uuid

from documentlm_core.db.session import get_session
from documentlm_core.schemas import PrimarySourceCreate, SourceType
from documentlm_core.services.source import (
    compute_content_hash,
    create_primary_source,
    delete_source,
    list_sources,
    reject_source,
    verify_source,
)
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from api.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Source intake page
# ---------------------------------------------------------------------------


@router.get("/topics/{topic_id}/sources", response_class=HTMLResponse)
async def get_sources_intake(
    request: Request,
    topic_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from documentlm_core.services.topic import get_topic

    topic = await get_topic(session, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    primary_sources = await list_sources(session, topic_id, primary_only=True)
    return templates.TemplateResponse(
        request,
        "sources/intake.html",
        {"topic": topic, "primary_sources": primary_sources},
    )


# ---------------------------------------------------------------------------
# Extract endpoint — all source types
# ---------------------------------------------------------------------------


@router.post("/topics/{topic_id}/sources/extract", response_class=HTMLResponse)
async def post_extract_source(
    request: Request,
    topic_id: uuid.UUID,
    source_type: str = Form(...),
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    text: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Extract a source and return an HTMX source card partial."""
    from documentlm_core.services.topic import get_topic

    topic = await get_topic(session, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    try:
        stype = SourceType(source_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown source_type: {source_type!r}"
        ) from exc

    try:
        title, content, source_url = await _extract(stype, file, url, text)
    except (ValueError, Exception) as exc:
        logger.exception(
            "Source extraction failed type=%s topic_id=%s", source_type, topic_id
        )
        return templates.TemplateResponse(
            request,
            "sources/_card.html",
            {"error": str(exc), "source_type": source_type},
            status_code=200,
        )

    content_hash = compute_content_hash(content)
    data = PrimarySourceCreate(
        topic_id=topic_id,
        source_type=stype,
        title=title,
        content=content,
        url=source_url,
        content_hash=content_hash,
    )
    source, was_duplicate = await create_primary_source(session, data)
    await session.commit()

    return templates.TemplateResponse(
        request,
        "sources/_card.html",
        {"source": source, "was_duplicate": was_duplicate},
    )


async def _extract(
    stype: SourceType,
    file: UploadFile | None,
    url: str | None,
    text: str | None,
) -> tuple[str, str, str | None]:
    """Return (title, content, url) for the given source type."""
    if stype == SourceType.PDF_UPLOAD:
        if file is None:
            raise ValueError("A file is required for PDF upload")
        from nlp_utils import extract_pdf_text_from_bytes

        data = await file.read()
        content = extract_pdf_text_from_bytes(data)
        title = (file.filename or "Uploaded PDF").removesuffix(".pdf")
        return title, content, None

    if stype == SourceType.URL_SCRAPE:
        if not url:
            raise ValueError("A URL is required for URL scraping")
        from urllib.parse import urlparse

        from nlp_utils import fetch_arxiv_text, fetch_pdf_text, fetch_url_text

        if "arxiv.org" in url:
            content = await fetch_arxiv_text(url)
        elif url.endswith(".pdf"):
            content = await fetch_pdf_text(url)
        else:
            content = await fetch_url_text(url)
        host = urlparse(url).netloc or url
        return host, content, url

    if stype == SourceType.YOUTUBE_TRANSCRIPT:
        if not url:
            raise ValueError("A URL is required for YouTube transcript")
        from nlp_utils import fetch_youtube_transcript

        title, content = await fetch_youtube_transcript(url)
        return title, content, url

    if stype == SourceType.RAW_TEXT:
        if not text or not text.strip():
            raise ValueError("Text content is required for raw text source")
        return "Pasted text", text.strip(), None

    raise ValueError(f"Unsupported source type: {stype}")


# ---------------------------------------------------------------------------
# Delete source
# ---------------------------------------------------------------------------


@router.delete("/topics/{topic_id}/sources/{source_id}", response_class=HTMLResponse)
async def delete_topic_source(
    topic_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await delete_source(session, source_id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return HTMLResponse(content="", status_code=200, headers={"HX-Trigger": "sourceDeleted"})


# ---------------------------------------------------------------------------
# Suggest sources (ArXiv + YouTube search, no DB writes)
# ---------------------------------------------------------------------------


@router.post("/topics/{topic_id}/sources/suggest", response_class=HTMLResponse)
async def suggest_sources(
    request: Request,
    topic_id: uuid.UUID,
    query: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Search the web for suggestions; return a card-list partial."""
    from documentlm_core.agents.academic_scout import search_web, search_youtube
    from documentlm_core.services.topic import get_topic

    topic = await get_topic(session, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    search_results = await search_web(query)
    youtube_results = await search_youtube(query)
    suggestions = search_results + youtube_results

    return templates.TemplateResponse(
        request,
        "sources/_suggestions.html",
        {"suggestions": suggestions, "topic_id": topic_id},
    )


# ---------------------------------------------------------------------------
# Legacy source queue management (verification / discovery)
# ---------------------------------------------------------------------------


@router.get("/topics/{topic_id}/sources/queue", response_class=HTMLResponse)
async def get_sources_queue(
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
