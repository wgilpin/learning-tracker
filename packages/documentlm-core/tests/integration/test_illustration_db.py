"""Integration tests for ChapterIllustration DB persistence.

Requires a real running PostgreSQL instance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from documentlm_core.db.models import AtomicChapter, ChapterIllustration, SyllabusItem, Topic, User
from documentlm_core.schemas import IllustrationRead
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def topic_with_chapter(async_session: AsyncSession, test_user: User) -> AtomicChapter:
    """Create a minimal topic → syllabus_item → chapter chain."""
    import bcrypt

    topic = Topic(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Test Topic",
        created_at=datetime.now(UTC),
    )
    async_session.add(topic)
    await async_session.flush()

    item = SyllabusItem(
        id=uuid.uuid4(),
        topic_id=topic.id,
        title="Test Item",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    async_session.add(item)
    await async_session.flush()

    chapter = AtomicChapter(
        id=uuid.uuid4(),
        topic_id=topic.id,
        syllabus_item_id=item.id,
        content="## Introduction\n\nTest content.",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    async_session.add(chapter)
    await async_session.flush()
    return chapter


class TestChapterIllustrationPersistence:
    @pytest.mark.asyncio
    async def test_insert_and_fetch_illustration(
        self, async_session: AsyncSession, topic_with_chapter: AtomicChapter
    ) -> None:
        fake_bytes = b"\x89PNG\r\n\x1a\nfakeimagedata"
        illustration = ChapterIllustration(
            id=uuid.uuid4(),
            chapter_id=topic_with_chapter.id,
            paragraph_index=1,
            image_data=fake_bytes,
            image_mime_type="image/png",
            image_description="A diagram of a neural network",
            created_at=datetime.now(UTC),
        )
        async_session.add(illustration)
        await async_session.flush()

        from sqlalchemy import select

        result = await async_session.execute(
            select(ChapterIllustration).where(
                ChapterIllustration.chapter_id == topic_with_chapter.id,
                ChapterIllustration.paragraph_index == 1,
            )
        )
        fetched = result.scalar_one()
        assert fetched.image_data == fake_bytes
        assert fetched.image_mime_type == "image/png"
        assert fetched.image_description == "A diagram of a neural network"

    @pytest.mark.asyncio
    async def test_unique_constraint_on_chapter_and_paragraph(
        self, async_session: AsyncSession, topic_with_chapter: AtomicChapter
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        ill1 = ChapterIllustration(
            id=uuid.uuid4(),
            chapter_id=topic_with_chapter.id,
            paragraph_index=2,
            image_data=b"IMG1",
            image_mime_type="image/png",
            image_description="First",
            created_at=datetime.now(UTC),
        )
        ill2 = ChapterIllustration(
            id=uuid.uuid4(),
            chapter_id=topic_with_chapter.id,
            paragraph_index=2,  # duplicate index — must fail
            image_data=b"IMG2",
            image_mime_type="image/jpeg",
            image_description="Second",
            created_at=datetime.now(UTC),
        )
        async_session.add(ill1)
        await async_session.flush()
        async_session.add(ill2)
        with pytest.raises(IntegrityError):
            await async_session.flush()

    @pytest.mark.asyncio
    async def test_illustration_read_schema_from_orm(
        self, async_session: AsyncSession, topic_with_chapter: AtomicChapter
    ) -> None:
        illustration = ChapterIllustration(
            id=uuid.uuid4(),
            chapter_id=topic_with_chapter.id,
            paragraph_index=3,
            image_data=b"TESTDATA",
            image_mime_type="image/jpeg",
            image_description="A chart",
            created_at=datetime.now(UTC),
        )
        async_session.add(illustration)
        await async_session.flush()

        read = IllustrationRead.model_validate(illustration)
        assert read.paragraph_index == 3
        assert read.image_mime_type == "image/jpeg"
        assert read.image_description == "A chart"
        assert read.chapter_id == topic_with_chapter.id
