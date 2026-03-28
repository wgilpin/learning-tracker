"""Source CRUD service: create with deduplication, list by topic, verify, reject."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Source
from documentlm_core.schemas import SourceCreate, SourceRead, SourceStatus

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
        verification_status=SourceStatus.QUEUED.value,
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


async def list_sources(session: AsyncSession, topic_id: uuid.UUID) -> list[SourceRead]:
    result = await session.execute(
        select(Source).where(Source.topic_id == topic_id).order_by(Source.created_at)
    )
    return [_to_read(s) for s in result.scalars().all()]


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
    return SourceRead(
        id=source.id,
        topic_id=source.topic_id,
        url=source.url,
        doi=source.doi,
        title=source.title,
        authors=list(source.authors),
        publication_date=source.publication_date,
        verification_status=SourceStatus(source.verification_status),
    )
