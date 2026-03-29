"""Academic Scout ADK agent: discovers sources via SerpApi and YouTube."""

from __future__ import annotations

import logging
import uuid
from typing import TypedDict

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.schemas import SourceCreate
from documentlm_core.services.pipeline import extract_and_index_source
from documentlm_core.services.source import create_source, list_sources

logger = logging.getLogger(__name__)


class _SourceResult(TypedDict, total=False):
    title: str
    url: str | None
    doi: str | None
    authors: list[str]


async def search_web(query: str, max_results: int = 5) -> list[_SourceResult]:
    """Search the web via SerpApi. HTTP calls are mockable in tests."""
    import os

    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        logger.info("SERPAPI_KEY not configured — skipping web search")
        return []

    params: dict[str, str | int] = {
        "q": query,
        "num": max_results,
        "api_key": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            if response.status_code == 429:
                logger.warning("SerpApi rate-limited for query=%r — skipping", query)
                return []
            response.raise_for_status()
        results: list[_SourceResult] = []
        for item in response.json().get("organic_results", [])[:max_results]:
            title = (item.get("title") or "").strip()
            url = item.get("link")
            if not title or not url:
                continue
            results.append({"title": title, "url": url, "doi": None, "authors": []})
        return results
    except Exception:
        logger.exception("SerpApi search failed for query=%r", query)
        return []


async def search_youtube(query: str, max_results: int = 3) -> list[_SourceResult]:
    """Search YouTube for educational videos. HTTP calls are mockable in tests.

    Note: Requires YOUTUBE_API_KEY env var in production. Returns empty list if not configured.
    """
    import os

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        logger.info("YOUTUBE_API_KEY not configured — skipping YouTube search")
        return []

    url = "https://www.googleapis.com/youtube/v3/search"
    params: dict[str, str | int] = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        data = response.json()
        results: list[_SourceResult] = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            results.append(
                {
                    "title": snippet.get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "doi": None,
                    "authors": [snippet.get("channelTitle", "")],
                }
            )
        return results
    except Exception:
        logger.exception("YouTube search failed for query=%r", query)
        return []


async def run_academic_scout(
    topic_id: uuid.UUID,
    topic_title: str,
    session: AsyncSession,
) -> list[uuid.UUID]:  # noqa: C901
    """Discover sources for a topic and persist them to the source queue.

    Returns the list of created/existing Source IDs. All HTTP calls (ArXiv, YouTube)
    are routed through `search_arxiv` and `search_youtube` — mock these in tests.
    """
    logger.info("Academic Scout starting for topic_id=%s title=%r", topic_id, topic_title)

    # Load primary sources first and log them before any external search
    primary_sources = await list_sources(session, topic_id, primary_only=True)
    if primary_sources:
        logger.info(
            "Academic Scout: %d primary source(s) present — processing before search",
            len(primary_sources),
        )

    logger.info("Academic Scout searching OpenAlex for %r", topic_title)
    arxiv_results = await search_web(topic_title)
    logger.info("Academic Scout web search returned %d results", len(arxiv_results))

    logger.info("Academic Scout searching YouTube for %r", topic_title)
    youtube_results = await search_youtube(topic_title)
    logger.info("Academic Scout YouTube returned %d results", len(youtube_results))

    all_results = arxiv_results + youtube_results
    logger.info("Academic Scout persisting %d discovered sources", len(all_results))
    created_ids: list[uuid.UUID] = []

    for result in all_results:
        title = (result.get("title") or "").strip()
        url = result.get("url") or None
        doi = result.get("doi") or None
        authors: list[str] = result.get("authors") or []

        if not title:
            continue
        if not url and not doi:
            continue

        try:
            logger.info("Academic Scout persisting source title=%r", title)
            source = await create_source(
                session,
                SourceCreate(
                    topic_id=topic_id,
                    url=str(url) if url else None,
                    doi=str(doi) if doi else None,
                    title=title,
                    authors=authors,
                ),
            )
            created_ids.append(source.id)
            logger.info("Academic Scout extracting and indexing source_id=%s", source.id)
            await extract_and_index_source(source.id, session)
            await session.commit()
        except Exception:
            logger.exception("Failed to persist source title=%r", title)

    logger.info(
        "Academic Scout completed topic_id=%s sources_created=%d",
        topic_id,
        len(created_ids),
    )
    return created_ids
