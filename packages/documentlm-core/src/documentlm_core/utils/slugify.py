"""Slug generation utilities."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def make_slug(title: str) -> str:
    """Convert a title to a URL-safe slug (lowercase alphanumeric + hyphens)."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "item"


async def unique_topic_slug(title: str, session: AsyncSession) -> str:
    """Return a slug for a topic that is unique across all topics.

    NOTE: there is a theoretical race condition — two concurrent requests could
    both find a slug free here and then both attempt to insert, hitting the
    unique constraint on topics.slug.  In practice this app is single-user so
    it doesn't matter, but if concurrent creation is ever needed, catch
    IntegrityError on session.flush() in create_topic and retry.
    """
    from documentlm_core.db.models import Topic

    base = make_slug(title)
    slug = base
    counter = 2
    while True:
        result = await session.execute(select(Topic.id).where(Topic.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{counter}"
        counter += 1


async def unique_chapter_slug(title: str, topic_id: uuid.UUID, session: AsyncSession) -> str:
    """Return a slug for a chapter that is unique within the given topic."""
    from documentlm_core.db.models import SyllabusItem

    base = make_slug(title)
    slug = base
    counter = 2
    while True:
        result = await session.execute(
            select(SyllabusItem.id).where(
                SyllabusItem.slug == slug,
                SyllabusItem.topic_id == topic_id,
            )
        )
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{counter}"
        counter += 1
