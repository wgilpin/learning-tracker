"""Source CRUD service: create with deduplication, list by topic, verify, reject."""

from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Source, UserSourceRef
from documentlm_core.schemas import (
    PrimarySourceCreate,
    SourceCreate,
    SourceRead,
    SourceStatus,
    SourceType,
)
from documentlm_core.services.chroma import delete_source_collection, get_chroma_client

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    """Return SHA-256 hex digest of text encoded as UTF-8."""
    return hashlib.sha256(text.encode()).hexdigest()


async def add_source_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    title: str,
    content: str,
    content_hash: str,
    source_type: str = SourceType.PDF_UPLOAD,
    url: str | None = None,
    authors: list[str] | None = None,
    is_primary: bool = True,
) -> tuple[Source, UserSourceRef, bool]:
    """Find-or-create a Source by content_hash, then create a UserSourceRef.

    Returns (source, ref, was_duplicate).
    ``was_duplicate`` is True if the Source already existed globally.
    """
    # 1. Find existing source by content_hash
    result = await session.execute(
        select(Source).where(Source.content_hash == content_hash)
    )
    existing = result.scalar_one_or_none()
    was_duplicate = existing is not None

    if existing is None:
        existing = Source(
            id=uuid.uuid4(),
            source_type=source_type,
            is_primary=is_primary,
            title=title,
            content=content,
            content_hash=content_hash,
            url=url,
            authors=authors or [],
            verification_status=SourceStatus.VERIFIED.value,
        )
        session.add(existing)
        try:
            await session.flush()
        except IntegrityError:
            # Race condition: another request inserted same hash first
            await session.rollback()
            result = await session.execute(
                select(Source).where(Source.content_hash == content_hash)
            )
            existing = result.scalar_one()
            was_duplicate = True

    # 2. Create UserSourceRef (idempotent via unique constraint)
    ref_result = await session.execute(
        select(UserSourceRef).where(
            UserSourceRef.user_id == user_id,
            UserSourceRef.source_id == existing.id,
            UserSourceRef.topic_id == topic_id,
        )
    )
    ref = ref_result.scalar_one_or_none()
    if ref is None:
        ref = UserSourceRef(
            id=uuid.uuid4(),
            user_id=user_id,
            source_id=existing.id,
            topic_id=topic_id,
        )
        session.add(ref)
        await session.flush()

    logger.info(
        "add_source_for_user source_id=%s user_id=%s topic_id=%s duplicate=%s",
        existing.id,
        user_id,
        topic_id,
        was_duplicate,
    )
    return existing, ref, was_duplicate


async def delete_source_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> bool:
    """Delete UserSourceRef for this user/topic. If no refs remain, delete Source + ChromaDB.

    Returns True if the Source row was deleted (ref_count reached zero).
    """
    # Delete the user's ref
    ref_result = await session.execute(
        select(UserSourceRef).where(
            UserSourceRef.user_id == user_id,
            UserSourceRef.source_id == source_id,
            UserSourceRef.topic_id == topic_id,
        )
    )
    ref = ref_result.scalar_one_or_none()
    if ref is None:
        logger.warning(
            "delete_source_for_user: ref not found source_id=%s user_id=%s topic_id=%s",
            source_id,
            user_id,
            topic_id,
        )
        return False

    await session.delete(ref)
    await session.flush()

    # Check remaining refs
    remaining = await session.scalar(
        select(func.count(UserSourceRef.id)).where(UserSourceRef.source_id == source_id)
    )

    if remaining == 0:
        # Delete the source row (cascades chapter_sources)
        source_result = await session.execute(select(Source).where(Source.id == source_id))
        source = source_result.scalar_one_or_none()
        if source is not None:
            await session.delete(source)
            await session.flush()

        # Remove ChromaDB collection
        try:
            client = get_chroma_client()
            delete_source_collection(client, source_id)
        except Exception:
            logger.exception("Failed to delete ChromaDB collection for source_id=%s", source_id)

        logger.info("Deleted source id=%s (ref_count=0)", source_id)
        return True

    logger.info(
        "Removed ref for source_id=%s user_id=%s; %s refs remaining",
        source_id,
        user_id,
        remaining,
    )
    return False


async def list_sources(
    session: AsyncSession,
    topic_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    primary_only: bool = False,
) -> list[SourceRead]:
    """List sources via UserSourceRef join, filtered by topic_id and optionally user_id."""
    stmt = (
        select(Source)
        .join(UserSourceRef, UserSourceRef.source_id == Source.id)
        .where(UserSourceRef.topic_id == topic_id)
    )
    if user_id is not None:
        stmt = stmt.where(UserSourceRef.user_id == user_id)
    if primary_only:
        stmt = stmt.where(Source.is_primary.is_(True))
    result = await session.execute(stmt.order_by(UserSourceRef.created_at))
    return [_to_read(s) for s in result.scalars().all()]


# ---------------------------------------------------------------------------
# Legacy functions (kept for backwards compatibility)
# ---------------------------------------------------------------------------


async def create_source(session: AsyncSession, data: SourceCreate) -> SourceRead:
    """Create a bibliographic source (no content). No deduplication by content_hash."""
    existing: Source | None = None
    if data.doi:
        result = await session.execute(select(Source).where(Source.doi == data.doi))
        existing = result.scalar_one_or_none()
    if existing is None and data.url:
        result = await session.execute(select(Source).where(Source.url == data.url))
        existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info("Duplicate source detected, returning existing id=%s", existing.id)
        return _to_read(existing)

    source = Source(
        id=uuid.uuid4(),
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
    logger.info("Created source id=%s", source.id)
    return _to_read(source)


async def create_primary_source(
    session: AsyncSession,
    data: PrimarySourceCreate,
) -> tuple[SourceRead, bool]:
    """Create a primary source with global deduplication by content_hash.

    Returns (source, was_duplicate).
    """
    existing: Source | None = None

    if data.source_type in (SourceType.PDF_UPLOAD, SourceType.RAW_TEXT):
        result = await session.execute(
            select(Source).where(Source.content_hash == data.content_hash)
        )
        existing = result.scalar_one_or_none()
    elif data.url:
        result = await session.execute(select(Source).where(Source.url == data.url))
        existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info("Duplicate primary source detected, returning existing id=%s", existing.id)
        return _to_read(existing), True

    source = Source(
        id=uuid.uuid4(),
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
    logger.info("Created primary source id=%s type=%s", source.id, data.source_type)
    return _to_read(source), False


async def delete_source(session: AsyncSession, source_id: uuid.UUID) -> None:
    """Delete a source by ID unconditionally. Raises ValueError if not found."""
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
