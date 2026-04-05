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


async def search_wikipedia(query: str, max_results: int = 3) -> list[_SourceResult]:
    """Search Wikipedia for articles matching the query.

    Uses the `wikipedia` PyPI package (synchronous — run in executor to avoid blocking).
    Returns empty list if the package is unavailable or the search fails.
    """
    import asyncio

    try:
        import wikipedia  # type: ignore[import-untyped]
    except ImportError:
        logger.info("wikipedia package not installed — skipping Wikipedia search")
        return []

    def _sync_search() -> list[_SourceResult]:
        results: list[_SourceResult] = []
        try:
            titles = wikipedia.search(query, results=max_results)
        except Exception:
            logger.exception("Wikipedia search failed for query=%r", query)
            return []

        for title in titles:
            try:
                page = wikipedia.page(title, auto_suggest=False)
                # Build a plain-text excerpt from the summary (first 2 000 chars)
                content = page.summary[:2000] if page.summary else ""
                if not content:
                    continue
                results.append(
                    {
                        "title": page.title,
                        "url": page.url,
                        "doi": None,
                        "authors": ["Wikipedia"],
                        "_content": content,  # type: ignore[typeddict-unknown-key]
                    }
                )
            except wikipedia.exceptions.DisambiguationError as e:
                # Try the first suggested option
                try:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                    content = page.summary[:2000] if page.summary else ""
                    if content:
                        results.append(
                            {
                                "title": page.title,
                                "url": page.url,
                                "doi": None,
                                "authors": ["Wikipedia"],
                                "_content": content,  # type: ignore[typeddict-unknown-key]
                            }
                        )
                except Exception:
                    pass
            except Exception:
                logger.debug("Wikipedia: could not fetch page %r", title)
        return results

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_search)


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

    logger.info("Academic Scout searching Wikipedia for %r", topic_title)
    wikipedia_results = await search_wikipedia(topic_title)
    logger.info("Academic Scout Wikipedia returned %d results", len(wikipedia_results))

    all_results = arxiv_results + youtube_results + wikipedia_results
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
        # Skip bare Wikipedia URLs from web search — search_wikipedia() handles
        # these with pre-fetched content, avoiding a redundant (and 403-prone) fetch.
        prefetched_content: str | None = result.get("_content")  # type: ignore[typeddict-item]
        if url and "wikipedia.org/wiki/" in url and not prefetched_content:
            logger.debug("Academic Scout skipping Wikipedia URL: %s", url)
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
            if prefetched_content:
                # Inject Wikipedia text directly so the pipeline skips HTTP fetching
                from documentlm_core.db.models import Source
                from documentlm_core.schemas import IndexStatus
                from documentlm_core.services.chroma import get_chroma_client, upsert_source_chunks
                from documentlm_core.services.pipeline import _chunk

                source_obj = await session.get(Source, source.id)
                if source_obj is not None and source_obj.index_status != IndexStatus.INDEXED:
                    chunks = _chunk(prefetched_content)
                    if chunks:
                        chroma_client = get_chroma_client()
                        upsert_source_chunks(chroma_client, source.id, chunks)
                        source_obj.content = prefetched_content
                        source_obj.index_status = IndexStatus.INDEXED
                        source_obj.index_error = None
                        logger.info(
                            "Academic Scout indexed Wikipedia source title=%r chunks=%d",
                            title,
                            len(chunks),
                        )
                        await session.flush()
            else:
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
