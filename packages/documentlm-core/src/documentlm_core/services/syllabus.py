"""Syllabus service: item CRUD with simple parent-child hierarchy."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import SyllabusItem
from documentlm_core.schemas import (
    SyllabusItemCreate,
    SyllabusItemRead,
    SyllabusItemStatusUpdate,
    SyllabusStatus,
)

logger = logging.getLogger(__name__)


async def create_syllabus_item(session: AsyncSession, data: SyllabusItemCreate) -> SyllabusItemRead:
    item = SyllabusItem(
        id=uuid.uuid4(),
        topic_id=data.topic_id,
        parent_id=data.parent_id,
        title=data.title,
        description=data.description,
        status=SyllabusStatus.UNRESEARCHED.value,
    )
    session.add(item)
    await session.flush()
    logger.info("Created syllabus item id=%s topic_id=%s", item.id, data.topic_id)
    return _item_to_read(item)


async def list_syllabus_items(session: AsyncSession, topic_id: uuid.UUID) -> list[SyllabusItemRead]:
    result = await session.execute(
        select(SyllabusItem)
        .where(SyllabusItem.topic_id == topic_id)
        .order_by(SyllabusItem.created_at)
    )
    return [_item_to_read(item) for item in result.scalars().all()]


async def list_top_level_items(session: AsyncSession, topic_id: uuid.UUID) -> list[SyllabusItemRead]:
    result = await session.execute(
        select(SyllabusItem)
        .where(SyllabusItem.topic_id == topic_id, SyllabusItem.parent_id.is_(None))
        .order_by(SyllabusItem.created_at)
    )
    return [_item_to_read(item) for item in result.scalars().all()]


async def list_children(session: AsyncSession, parent_id: uuid.UUID) -> list[SyllabusItemRead]:
    result = await session.execute(
        select(SyllabusItem)
        .where(SyllabusItem.parent_id == parent_id)
        .order_by(SyllabusItem.created_at)
    )
    return [_item_to_read(item) for item in result.scalars().all()]


async def update_status(
    session: AsyncSession, item_id: uuid.UUID, update: SyllabusItemStatusUpdate
) -> SyllabusItemRead:
    result = await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise ValueError(f"SyllabusItem {item_id} not found")

    item.status = update.status.value
    await session.flush()
    logger.info("Updated status item_id=%s status=%s", item_id, update.status)
    return _item_to_read(item)


def _item_to_read(item: SyllabusItem) -> SyllabusItemRead:
    return SyllabusItemRead(
        id=item.id,
        topic_id=item.topic_id,
        parent_id=item.parent_id,
        title=item.title,
        description=item.description,
        status=SyllabusStatus(item.status),
    )
