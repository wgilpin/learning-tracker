"""Topic CRUD service."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Topic
from documentlm_core.schemas import TopicCreate, TopicRead

logger = logging.getLogger(__name__)


async def create_topic(
    session: AsyncSession, data: TopicCreate, user_id: uuid.UUID
) -> TopicRead:
    topic = Topic(
        id=uuid.uuid4(),
        user_id=user_id,
        title=data.title,
        description=data.description,
    )
    session.add(topic)
    await session.flush()
    logger.info("Created topic id=%s title=%r user_id=%s", topic.id, topic.title, user_id)
    return _to_read(topic)


async def get_topic(
    session: AsyncSession, topic_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> TopicRead | None:
    stmt = select(Topic).where(Topic.id == topic_id)
    if user_id is not None:
        stmt = stmt.where(Topic.user_id == user_id)
    result = await session.execute(stmt)
    topic = result.scalar_one_or_none()
    if topic is None:
        return None
    return _to_read(topic)


async def list_topics(
    session: AsyncSession, user_id: uuid.UUID | None = None
) -> list[TopicRead]:
    stmt = select(Topic).order_by(Topic.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(Topic.user_id == user_id)
    result = await session.execute(stmt)
    return [_to_read(t) for t in result.scalars().all()]


async def delete_topic(
    session: AsyncSession, topic_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> bool:
    """Delete a topic. Returns True if deleted, False if not found (or not owned)."""
    stmt = select(Topic).where(Topic.id == topic_id)
    if user_id is not None:
        stmt = stmt.where(Topic.user_id == user_id)
    result = await session.execute(stmt)
    topic = result.scalar_one_or_none()
    if topic is None:
        return False
    await session.delete(topic)
    await session.flush()
    logger.info("Deleted topic id=%s", topic_id)
    return True


def _to_read(topic: Topic) -> TopicRead:
    return TopicRead(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        created_at=topic.created_at,
    )
