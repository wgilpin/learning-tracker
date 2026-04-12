"""Data migration 001: backfill learning objectives for existing syllabus chapters.

Targets all leaf SyllabusItems (parent_id IS NOT NULL) that have no
learning_objectives yet — i.e. topics created before this feature was added.

Idempotent: items already populated are skipped.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

description = "Backfill Bloom's taxonomy learning objectives for existing syllabus chapters"


async def run(session: AsyncSession) -> int:
    from documentlm_core.agents.syllabus_architect import generate_chapter_objectives
    from documentlm_core.db.models import SyllabusItem, Topic

    # Leaf items (children) without objectives
    result = await session.execute(
        select(SyllabusItem).where(
            SyllabusItem.parent_id.isnot(None),
            SyllabusItem.learning_objectives.is_(None),
        )
    )
    items = result.scalars().all()

    if not items:
        return 0

    # Bulk-load topics to avoid N+1 queries
    topic_ids = {item.topic_id for item in items}
    topics_result = await session.execute(
        select(Topic).where(Topic.id.in_(topic_ids))
    )
    topics_by_id = {t.id: t for t in topics_result.scalars().all()}

    processed = 0

    async def _process(item: SyllabusItem) -> None:
        nonlocal processed
        topic = topics_by_id.get(item.topic_id)
        if topic is None:
            logger.warning("backfill: topic not found for item_id=%s — skipping", item.id)
            return
        try:
            objectives = await generate_chapter_objectives(
                topic_title=topic.title,
                topic_level=topic.level or "intermediate",
                item_title=item.title,
                item_description=item.description,
            )
        except Exception:
            logger.exception(
                "backfill: objectives generation failed for item_id=%s — skipping", item.id
            )
            return

        if objectives:
            item.learning_objectives = objectives
            item.objectives_mastered = [False] * len(objectives)
            processed += 1
            logger.info(
                "backfill: %d objectives written for item_id=%s title=%r",
                len(objectives),
                item.id,
                item.title,
            )

    # Run per-item LLM calls concurrently — one gather per topic-group to
    # avoid overwhelming the API quota on very large syllabi.
    BATCH_SIZE = 5
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        await asyncio.gather(*[_process(item) for item in batch])
        await session.flush()
        logger.info("backfill: flushed batch %d-%d", i, i + len(batch))

    return processed
