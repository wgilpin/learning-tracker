"""Integration tests for topic creation and syllabus retrieval."""

from __future__ import annotations

import uuid

import pytest
from documentlm_core.schemas import SyllabusItemCreate, TopicCreate
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_topic(async_session: AsyncSession, test_user) -> None:
    from documentlm_core.services.topic import create_topic

    result = await create_topic(async_session, TopicCreate(title="Quantum Mechanics"), user_id=test_user.id)
    assert result.id is not None
    assert result.title == "Quantum Mechanics"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_topic(async_session: AsyncSession, test_user) -> None:
    from documentlm_core.services.topic import create_topic, get_topic

    created = await create_topic(async_session, TopicCreate(title="Linear Algebra"), user_id=test_user.id)
    fetched = await get_topic(async_session, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Linear Algebra"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_topic_not_found(async_session: AsyncSession) -> None:
    from documentlm_core.services.topic import get_topic

    result = await get_topic(async_session, uuid.uuid4())
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_topics(async_session: AsyncSession, test_user) -> None:
    from documentlm_core.services.topic import create_topic, list_topics

    await create_topic(async_session, TopicCreate(title="Topic A"), user_id=test_user.id)
    await create_topic(async_session, TopicCreate(title="Topic B"), user_id=test_user.id)
    topics = await list_topics(async_session, user_id=test_user.id)
    titles = [t.title for t in topics]
    assert "Topic A" in titles
    assert "Topic B" in titles


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_syllabus_item_no_parent(async_session: AsyncSession, test_user) -> None:
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Test Topic"), user_id=test_user.id)
    item = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Introduction"),
    )
    assert item.id is not None
    assert item.topic_id == topic.id
    assert item.parent_id is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_syllabus_item_with_parent(async_session: AsyncSession, test_user) -> None:
    from documentlm_core.services.syllabus import create_syllabus_item
    from documentlm_core.services.topic import create_topic

    topic = await create_topic(async_session, TopicCreate(title="Test Topic 2"), user_id=test_user.id)
    parent = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Section 1"),
    )
    child = await create_syllabus_item(
        async_session,
        SyllabusItemCreate(topic_id=topic.id, title="Section 1.1", parent_id=parent.id),
    )
    assert child.parent_id == parent.id
