"""Source CRUD service: create with deduplication, list by topic, verify, reject."""

from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Source
from documentlm_core.schemas import (
    PrimarySourceCreate,
    SourceCreate,
    SourceRead,
    SourceStatus,
    SourceType,
)

logger = logging.getLogger(__name__)


async def create_source(session: AsyncSession, data: SourceCreate) -> SourceRead:
    """Create a source, skipping duplicates (returns existing on conflict)."""
    # Deduplication: check by DOI first, then URL
    existing: Source | None = None
    if data.doi:
        result = await session.execute(
            select(Source).where(
                Source.topic_id == data.topic_id,
                Source.doi == data.doi,
            )
        )
        existing = result.scalar_one_or_none()
    if existing is None and data.url:
        result = await session.execute(
            select(Source).where(
                Source.topic_id == data.topic_id,
                Source.url == data.url,
            )
        )
        existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info("Duplicate source detected, returning existing id=%s", existing.id)
        return _to_read(existing)

    source = Source(
        id=uuid.uuid4(),
        topic_id=data.topic_id,
        url=data.url,
        doi=data.doi,
        title=data.title,
        authors=data.authors,
        publication_date=data.publication_date,
    )
    session.add(source)
    try:
        await session.flush()
    except IntegrityError:
        logger.exception("IntegrityError creating source — possible race condition")
        await session.rollback()
        raise
    logger.info("Created source id=%s topic_id=%s", source.id, source.topic_id)
    return _to_read(source)


def compute_content_hash(text: str) -> str:
    """Return SHA-256 hex digest of text encoded as UTF-8."""
    return hashlib.sha256(text.encode()).hexdigest()


async def list_sources(
    session: AsyncSession,
    topic_id: uuid.UUID,
    primary_only: bool = False,
) -> list[SourceRead]:
    stmt = select(Source).where(Source.topic_id == topic_id)
    if primary_only:
        stmt = stmt.where(Source.is_primary.is_(True))
    result = await session.execute(stmt.order_by(Source.created_at))
    return [_to_read(s) for s in result.scalars().all()]


async def create_primary_source(
    session: AsyncSession,
    data: PrimarySourceCreate,
) -> tuple[SourceRead, bool]:
    """Create a primary source with deduplication.

    Returns (source, was_duplicate).
    - PDF_UPLOAD / RAW_TEXT: deduplicated by (topic_id, content_hash)
    - URL_SCRAPE / YOUTUBE_TRANSCRIPT: deduplicated by (topic_id, url)
    """
    existing: Source | None = None

    if data.source_type in (SourceType.PDF_UPLOAD, SourceType.RAW_TEXT):
        result = await session.execute(
            select(Source).where(
                Source.topic_id == data.topic_id,
                Source.content_hash == data.content_hash,
            )
        )
        existing = result.scalar_one_or_none()
    elif data.url:
        result = await session.execute(
            select(Source).where(
                Source.topic_id == data.topic_id,
                Source.url == data.url,
            )
        )
        existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info("Duplicate primary source detected, returning existing id=%s", existing.id)
        return _to_read(existing), True

    source = Source(
        id=uuid.uuid4(),
        topic_id=data.topic_id,
        source_type=data.source_type.value,
        is_primary=True,
        title=data.title,
        content=data.content,
        content_hash=data.content_hash,
        url=data.url,
        authors=data.authors,
        verification_status=SourceStatus.VERIFIED.value,
    )
    session.add(source)
    try:
        await session.flush()
    except IntegrityError:
        logger.exception("IntegrityError creating primary source — possible race condition")
        await session.rollback()
        raise
    logger.info(
        "Created primary source id=%s type=%s topic_id=%s",
        source.id,
        data.source_type,
        data.topic_id,
    )
    return _to_read(source), False


async def delete_source(session: AsyncSession, source_id: uuid.UUID) -> None:
    """Delete a source by ID. Raises ValueError if not found."""
    source = await _get_or_raise(session, source_id)
    await session.delete(source)
    await session.flush()
    logger.info("Deleted source id=%s", source_id)


async def verify_source(session: AsyncSession, source_id: uuid.UUID) -> SourceRead:
    source = await _get_or_raise(session, source_id)
    source.verification_status = SourceStatus.VERIFIED.value
    await session.flush()
    logger.info("Source verified id=%s", source_id)
    return _to_read(source)


async def reject_source(session: AsyncSession, source_id: uuid.UUID) -> SourceRead:
    source = await _get_or_raise(session, source_id)
    source.verification_status = SourceStatus.REJECTED.value
    await session.flush()
    logger.info("Source rejected id=%s", source_id)
    return _to_read(source)


async def _get_or_raise(session: AsyncSession, source_id: uuid.UUID) -> Source:
    result = await session.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise ValueError(f"Source {source_id} not found")
    return source


def _to_read(source: Source) -> SourceRead:
    return SourceRead.model_validate(source)
