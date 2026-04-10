"""Topic CRUD service."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Topic
from documentlm_core.schemas import TopicCreate, TopicRead
from documentlm_core.utils.slugify import unique_topic_slug

logger = logging.getLogger(__name__)


async def create_topic(
    session: AsyncSession, data: TopicCreate, user_id: uuid.UUID
) -> TopicRead:
    slug = await unique_topic_slug(data.title, session)
    topic = Topic(
        id=uuid.uuid4(),
        user_id=user_id,
        title=data.title,
        slug=slug,
        description=data.description,
        level=data.level,
    )
    session.add(topic)
    await session.flush()
    logger.info("Created topic id=%s title=%r slug=%r user_id=%s", topic.id, topic.title, slug, user_id)
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


async def get_topic_by_slug(
    session: AsyncSession, slug: str, user_id: uuid.UUID | None = None
) -> TopicRead | None:
    stmt = select(Topic).where(Topic.slug == slug)
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


async def update_topic_level(
    session: AsyncSession, topic_id: uuid.UUID, level: str, user_id: uuid.UUID | None = None
) -> bool:
    """Update the level field of a topic. Returns True if found and updated."""
    stmt = select(Topic).where(Topic.id == topic_id)
    if user_id is not None:
        stmt = stmt.where(Topic.user_id == user_id)
    result = await session.execute(stmt)
    topic = result.scalar_one_or_none()
    if topic is None:
        return False
    topic.level = level
    await session.flush()
    return True


def _to_read(topic: Topic) -> TopicRead:
    return TopicRead(
        id=topic.id,
        title=topic.title,
        slug=topic.slug,
        description=topic.description,
        level=topic.level,
        created_at=topic.created_at,
    )
