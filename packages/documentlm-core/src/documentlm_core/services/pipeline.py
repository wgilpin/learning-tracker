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
        logger.exception("extract_and_index_source: failed source_id=%s", source_id)

    await session.flush()


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
    return await fetch_url_text(url)


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
