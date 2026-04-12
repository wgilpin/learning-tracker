"""Syllabus service: item CRUD with simple parent-child hierarchy."""

from __future__ import annotations

import logging
import uuid

from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.config import settings
from documentlm_core.db.models import SyllabusItem
from documentlm_core.utils.slugify import unique_chapter_slug
from documentlm_core.schemas import (
    LearningObjective,
    SyllabusItemCreate,
    SyllabusItemRead,
    SyllabusItemStatusUpdate,
    SyllabusItemUpdate,
    SyllabusStatus,
)

logger = logging.getLogger(__name__)


async def create_syllabus_item(session: AsyncSession, data: SyllabusItemCreate) -> SyllabusItemRead:
    slug = await unique_chapter_slug(data.title, data.topic_id, session)
    item = SyllabusItem(
        id=uuid.uuid4(),
        topic_id=data.topic_id,
        parent_id=data.parent_id,
        title=data.title,
        slug=slug,
        description=data.description,
        status=SyllabusStatus.UNRESEARCHED.value,
    )
    session.add(item)
    await session.flush()
    logger.info("Created syllabus item id=%s topic_id=%s slug=%r", item.id, data.topic_id, slug)
    return _item_to_read(item)


async def list_syllabus_items(session: AsyncSession, topic_id: uuid.UUID) -> list[SyllabusItemRead]:
    result = await session.execute(
        select(SyllabusItem)
        .where(SyllabusItem.topic_id == topic_id)
        .order_by(SyllabusItem.created_at)
    )
    return [_item_to_read(item) for item in result.scalars().all()]


async def list_top_level_items(
    session: AsyncSession, topic_id: uuid.UUID
) -> list[SyllabusItemRead]:
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


async def get_ancestor_ids(session: AsyncSession, item_id: uuid.UUID) -> list[uuid.UUID]:
    """Return IDs of ancestors from root down to item's parent (not including item itself)."""
    ancestors: list[uuid.UUID] = []
    current_id = item_id
    while True:
        row = (await session.execute(
            select(SyllabusItem.parent_id).where(SyllabusItem.id == current_id)
        )).one_or_none()
        if row is None or row[0] is None:
            break
        ancestors.append(row[0])
        current_id = row[0]
    ancestors.reverse()
    return ancestors


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


async def has_duplicate_title(
    session: AsyncSession,
    topic_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    title: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    """Return True if a sibling item (same topic + parent) shares the given title."""
    stmt = select(SyllabusItem).where(
        SyllabusItem.topic_id == topic_id,
        SyllabusItem.title == title,
    )
    if parent_id is None:
        stmt = stmt.where(SyllabusItem.parent_id.is_(None))
    else:
        stmt = stmt.where(SyllabusItem.parent_id == parent_id)
    if exclude_id is not None:
        stmt = stmt.where(SyllabusItem.id != exclude_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def update_syllabus_item(
    session: AsyncSession,
    item_id: uuid.UUID,
    update: SyllabusItemUpdate,
) -> SyllabusItemRead:
    result = await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise ValueError(f"SyllabusItem {item_id} not found")

    if update.title is not None:
        stripped = update.title.strip()
        if not stripped:
            raise ValueError("Title must not be empty")
        item.title = stripped

    if update.description is not None:
        item.description = update.description

    await session.flush()
    logger.info("Updated syllabus item id=%s", item_id)
    return _item_to_read(item)


async def has_associated_content(
    session: AsyncSession,
    item_id: uuid.UUID,
) -> bool:
    """Return True if item has a linked AtomicChapter or any child items."""
    from documentlm_core.db.models import AtomicChapter

    chapter_result = await session.execute(
        select(AtomicChapter).where(AtomicChapter.syllabus_item_id == item_id)
    )
    if chapter_result.scalar_one_or_none() is not None:
        return True

    children_result = await session.execute(
        select(SyllabusItem).where(SyllabusItem.parent_id == item_id)
    )
    return children_result.scalar_one_or_none() is not None


async def mark_all_objectives_mastered(
    session: AsyncSession,
    item_id: uuid.UUID,
) -> None:
    """Mark every learning objective on a syllabus item as mastered."""
    result = await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None or not item.learning_objectives:
        return
    item.objectives_mastered = [True] * len(item.learning_objectives)
    await session.flush()
    logger.info("Marked all objectives mastered for item_id=%s", item_id)


async def delete_syllabus_item(
    session: AsyncSession,
    item_id: uuid.UUID,
) -> None:
    result = await session.execute(select(SyllabusItem).where(SyllabusItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise ValueError(f"SyllabusItem {item_id} not found")
    await session.delete(item)
    await session.flush()
    logger.info("Deleted syllabus item id=%s", item_id)


def _get_genai_client() -> genai.Client:
    return genai.Client(api_key=settings.google_api_key)


async def generate_item_description(
    session: AsyncSession,
    topic_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    title: str,
) -> str:
    """Generate a description using sibling context for a chapter in a syllabus."""
    parent_filter = (
        SyllabusItem.parent_id == parent_id
        if parent_id is not None
        else SyllabusItem.parent_id.is_(None)
    )
    siblings_result = await session.execute(
        select(SyllabusItem).where(SyllabusItem.topic_id == topic_id, parent_filter)
    )
    sibling_items = siblings_result.scalars().all()

    context_lines: list[str] = []
    for sib in sibling_items:
        if sib.description:
            context_lines.append(f"- {sib.title}: {sib.description}")
        else:
            context_lines.append(f"- {sib.title}")

    context_block = "\n".join(context_lines) if context_lines else "(no siblings yet)"
    prompt = (
        f"You are writing a short description for a study syllabus chapter titled '{title}'.\n"
        f"Other chapters in this section:\n{context_block}\n\n"
        f"Write a concise 1–3 sentence description for '{title}' that helps a student "
        f"understand what they will learn. Do not repeat the title."
    )

    try:
        client = _get_genai_client()
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        text: str = response.text or ""
        return text
    except Exception as exc:
        logger.exception("Gemini generation failed for topic_id=%s: %s", topic_id, exc)
        raise RuntimeError("Description generation failed") from exc


def _item_to_read(item: SyllabusItem) -> SyllabusItemRead:
    objectives = None
    if item.learning_objectives is not None:
        objectives = [LearningObjective(**o) for o in item.learning_objectives]
    return SyllabusItemRead(
        id=item.id,
        topic_id=item.topic_id,
        parent_id=item.parent_id,
        title=item.title,
        slug=item.slug,
        description=item.description,
        status=SyllabusStatus(item.status),
        learning_objectives=objectives,
        objectives_mastered=item.objectives_mastered,
    )
