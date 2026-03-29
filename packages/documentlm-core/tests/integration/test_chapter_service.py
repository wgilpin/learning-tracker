"""Integration tests for chapter creation and retrieval."""

from __future__ import annotations

import pytest
from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_and_get_chapter(async_session: AsyncSession) -> None:
    from documentlm_core.services.chapter import create_chapter, get_chapter
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Chapter Test"))
    item = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="No Prereqs")
    )

    chapter = await create_chapter(async_session, item.id, topic.id, "Chapter content", [])
    assert chapter.content == "Chapter content"

    fetched = await get_chapter(async_session, chapter.id)
    assert fetched is not None
    assert fetched.id == chapter.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_chapter_for_child_item(async_session: AsyncSession) -> None:
    """Chapter creation succeeds for a child item (parent-blocking is enforced at router level)."""
    from documentlm_core.services.chapter import create_chapter
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Child Item Test"))
    parent = await create_syllabus_item(
        async_session, SyllabusItemCreate(topic_id=topic.id, title="Parent")
    )
    child = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Child", parent_id=parent.id),
    )

    chapter = await create_chapter(async_session, child.id, topic.id, "content", [])
    assert chapter.content == "content"
    assert chapter.syllabus_item_id == child.id
