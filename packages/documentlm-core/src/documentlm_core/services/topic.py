"""Topic CRUD service."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Topic
from documentlm_core.schemas import TopicCreate, TopicRead

logger = logging.getLogger(__name__)


async def create_topic(session: AsyncSession, data: TopicCreate) -> TopicRead:
    topic = Topic(
        id=uuid.uuid4(),
        title=data.title,
        description=data.description,
    )
    session.add(topic)
    await session.flush()
    logger.info("Created topic id=%s title=%r", topic.id, topic.title)
    return _to_read(topic)


async def get_topic(session: AsyncSession, topic_id: uuid.UUID) -> TopicRead | None:
    result = await session.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if topic is None:
        return None
    return _to_read(topic)


async def list_topics(session: AsyncSession) -> list[TopicRead]:
    result = await session.execute(select(Topic).order_by(Topic.created_at.desc()))
    return [_to_read(t) for t in result.scalars().all()]


async def delete_topic(session: AsyncSession, topic_id: uuid.UUID) -> None:
    result = await session.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if topic is None:
        return
    await session.delete(topic)
    await session.flush()
    logger.info("Deleted topic id=%s", topic_id)


def _to_read(topic: Topic) -> TopicRead:
    return TopicRead(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        created_at=topic.created_at,
    )
