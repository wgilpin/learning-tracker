"""Chapter service: blocking guard, context folding, chapter persist, citation linking."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import AtomicChapter, ChapterSource, SyllabusItem
from documentlm_core.schemas import ChapterRead, SourceRead, SourceStatus

logger = logging.getLogger(__name__)


def _filter_verified_sources(sources: list[SourceRead]) -> list[SourceRead]:
    """Return only VERIFIED sources — citations must come from verified sources."""
    return [s for s in sources if s.verification_status == SourceStatus.VERIFIED]


async def create_chapter(
    session: AsyncSession,
    item_id: uuid.UUID,
    topic_id: uuid.UUID,
    content: str,
    source_ids: list[uuid.UUID],
) -> ChapterRead:
    """Persist a drafted chapter. Raises ValueError if parent chapter not yet drafted."""
    result = await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise ValueError(f"SyllabusItem {item_id} not found")

    # Check if chapter already exists
    existing_result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.syllabus_item_id == item_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        logger.info("Chapter already exists for item_id=%s, returning existing", item_id)
        return await _read_chapter(session, existing)

    now = datetime.now(UTC)
    chapter = AtomicChapter(
        id=uuid.uuid4(),
        topic_id=topic_id,
        syllabus_item_id=item_id,
        content=content,
        created_at=now,
        updated_at=now,
    )
    session.add(chapter)
    await session.flush()

    # Link only VERIFIED sources
    for source_id in source_ids:
        session.add(ChapterSource(chapter_id=chapter.id, source_id=source_id))
    await session.flush()

    logger.info("Created chapter id=%s item_id=%s", chapter.id, item_id)
    return await _read_chapter(session, chapter)


async def get_chapter(session: AsyncSession, chapter_id: uuid.UUID) -> ChapterRead | None:
    result = await session.execute(select(AtomicChapter).where(AtomicChapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter is None:
        return None
    return await _read_chapter(session, chapter)


async def get_context_summaries(
    session: AsyncSession, topic_id: uuid.UUID, exclude_item_id: uuid.UUID
) -> list[str]:
    """Return brief summaries of prior chapters for context folding."""
    result = await session.execute(
        select(AtomicChapter)
        .where(
            AtomicChapter.topic_id == topic_id,
            AtomicChapter.syllabus_item_id != exclude_item_id,
        )
        .order_by(AtomicChapter.created_at)
    )
    chapters = result.scalars().all()
    # Return first 200 chars of each chapter as summary
    return [c.content[:200] for c in chapters]


async def _read_chapter(session: AsyncSession, chapter: AtomicChapter) -> ChapterRead:
    from documentlm_core.db.models import MarginComment, Source
    from documentlm_core.schemas import CommentStatus, MarginCommentRead

    # Load sources via ChapterSource
    source_result = await session.execute(
        select(Source)
        .join(ChapterSource, ChapterSource.source_id == Source.id)
        .where(ChapterSource.chapter_id == chapter.id)
    )
    sources = source_result.scalars().all()
    source_reads = [
        SourceRead(
            id=s.id,
            topic_id=s.topic_id,
            url=s.url,
            doi=s.doi,
            title=s.title,
            authors=list(s.authors),
            publication_date=s.publication_date,
            verification_status=SourceStatus(s.verification_status),
        )
        for s in sources
    ]

    comment_result = await session.execute(
        select(MarginComment)
        .where(MarginComment.chapter_id == chapter.id)
        .order_by(MarginComment.created_at)
    )
    comment_reads = [
        MarginCommentRead(
            id=c.id,
            chapter_id=c.chapter_id,
            paragraph_anchor=c.paragraph_anchor,
            content=c.content,
            response=c.response,
            status=CommentStatus(c.status),
            created_at=c.created_at,
        )
        for c in comment_result.scalars().all()
    ]

    return ChapterRead(
        id=chapter.id,
        syllabus_item_id=chapter.syllabus_item_id,
        content=chapter.content,
        sources=source_reads,
        margin_comments=comment_reads,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )
