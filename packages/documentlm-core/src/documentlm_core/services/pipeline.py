"""Source extraction and indexing pipeline.

Dispatches by source_type, chunks extracted text via nlp_utils, and upserts
chunks into ChromaDB. Never raises — sets index_status=FAILED on any error.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Source
from documentlm_core.schemas import IndexStatus, SourceType
from documentlm_core.services.chroma import get_chroma_client, upsert_source_chunks

logger = logging.getLogger(__name__)


async def extract_and_index_source(
    source_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """Extract text from a source and upsert chunks into ChromaDB.

    Idempotent: returns immediately if source.index_status == INDEXED.
    On failure: sets index_status=FAILED, populates index_error, logs with
    traceback. Never raises. Flushes DB changes; does NOT commit — caller is
    responsible for committing the session.
    """
    from sqlalchemy import select

    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        logger.error("extract_and_index_source: Source %s not found — skipping", source_id)
        return

    if source.index_status == IndexStatus.INDEXED:
        logger.info(
            "extract_and_index_source: Source %s already indexed, skipping", source_id
        )
        return

    logger.info(
        "extract_and_index_source: starting source_id=%s source_type=%s",
        source_id,
        source.source_type,
    )

    try:
        text = await _extract_text(source)
        if text is None:
            raise ValueError(_no_text_reason(source))

        chunks = _chunk(text)
        if not chunks:
            raise ValueError("Extraction produced no text chunks")

        chroma_client = get_chroma_client()
        upsert_source_chunks(chroma_client, source_id, chunks)

        source.content = text
        source.index_status = IndexStatus.INDEXED
        source.index_error = None
        logger.info(
            "extract_and_index_source: succeeded source_id=%s chunks=%d",
            source_id,
            len(chunks),
        )

    except Exception as exc:
        source.index_status = IndexStatus.FAILED
        source.index_error = str(exc)
        # Expected failures (paywalled/bot-blocking sites, unscrapable pages) — warning only
        if _is_expected_extraction_failure(exc):
            logger.warning(
                "extract_and_index_source: skipped source_id=%s url=%s — %s",
                source_id,
                getattr(source, "url", None),
                exc,
            )
        else:
            logger.exception("extract_and_index_source: failed source_id=%s", source_id)

    await session.flush()


def _is_expected_extraction_failure(exc: BaseException) -> bool:
    """Return True for failures that are expected (blocked sites, unscrapable pages).

    These are logged as WARNING without a stack trace. Unexpected failures
    (connection errors, crashes) still use logger.exception.
    """
    # HTTP 4xx client errors — paywalled, bot-blocked, not found, etc.
    try:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
            return True
    except ImportError:
        pass
    # ValueError raised explicitly by fetchers when no text could be extracted
    if isinstance(exc, ValueError):
        return True
    return False


def _chunk(text: str) -> list[str]:
    from nlp_utils.chunker import chunk_sentences

    return chunk_sentences(text, chunk_size=500, chunk_overlap=50)


async def _extract_text(source: Source) -> str | None:
    if source.source_type in (SourceType.PDF_UPLOAD, SourceType.RAW_TEXT):
        return source.content  # already stored; may be None if empty

    if source.source_type == SourceType.URL_SCRAPE or (
        source.source_type == SourceType.SEARCH and source.url
    ):
        return await _fetch_url(source.url)

    if source.source_type == SourceType.YOUTUBE_TRANSCRIPT:
        return await _fetch_youtube(source.url)

    return None  # SEARCH with no URL — handled by _no_text_reason


def _no_text_reason(source: Source) -> str:
    if source.source_type == SourceType.SEARCH and not source.url:
        return "No URL to fetch for DOI-only source"
    return f"No extraction method for source_type={source.source_type}"


async def _fetch_url(url: str | None) -> str | None:
    if not url:
        return None
    from nlp_utils.fetcher import fetch_arxiv_text, fetch_pdf_text, fetch_url_text

    if "arxiv.org" in url:
        return await fetch_arxiv_text(url)
    if url.endswith(".pdf"):
        return await fetch_pdf_text(url)
    if "wikipedia.org/wiki/" in url:
        return await _fetch_wikipedia(url)
    return await fetch_url_text(url)


async def _fetch_wikipedia(url: str) -> str | None:
    """Fetch a Wikipedia article via the wikipedia PyPI package (uses the API, not scraping)."""
    import asyncio

    try:
        import wikipedia  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("wikipedia package not installed — falling back to URL scrape for %s", url)
        from nlp_utils.fetcher import fetch_url_text
        return await fetch_url_text(url)

    # Derive the page title from the URL path, e.g. /wiki/Graph_theory → "Graph theory"
    path = url.split("/wiki/", 1)[-1].split("#")[0]
    title = path.replace("_", " ")

    def _sync_fetch() -> str | None:
        try:
            page = wikipedia.page(title, auto_suggest=False)
            return page.content or None
        except wikipedia.exceptions.DisambiguationError as e:
            try:
                page = wikipedia.page(e.options[0], auto_suggest=False)
                return page.content or None
            except Exception:
                return None
        except Exception:
            logger.warning("wikipedia package failed to fetch %r", url)
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch)


async def _fetch_youtube(url: str | None) -> str | None:
    if not url:
        return None
    try:
        from nlp_utils.youtube import fetch_youtube_transcript  # type: ignore[attr-defined]

        return await fetch_youtube_transcript(url)
    except (ImportError, AttributeError) as exc:
        raise ValueError(
            "fetch_youtube_transcript not available — requires Feature 002 nlp_utils extensions"
        ) from exc
