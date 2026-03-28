"""Syllabus Architect: generates a hierarchical syllabus for a topic."""

from __future__ import annotations

import logging
import uuid
from typing import Protocol

logger = logging.getLogger(__name__)


class SyllabusToolsProtocol(Protocol):
    async def create_syllabus_item(
        self,
        topic_id: uuid.UUID,
        title: str,
        description: str | None,
        parent_id: uuid.UUID | None,
    ) -> uuid.UUID:
        """Persist a syllabus item and return its ID."""
        ...


async def run_syllabus_architect(
    topic_id: uuid.UUID,
    topic_title: str,
    tools: SyllabusToolsProtocol,
) -> list[uuid.UUID]:
    logger.info("Syllabus Architect starting for topic_id=%s title=%r", topic_id, topic_title)
    root_id = await tools.create_syllabus_item(
        topic_id=topic_id,
        title="Foundations",
        description=f"Core prerequisites for {topic_title}",
        parent_id=None,
    )
    child1_id = await tools.create_syllabus_item(
        topic_id=topic_id,
        title="Core Concepts",
        description=f"Central ideas in {topic_title}",
        parent_id=root_id,
    )
    await tools.create_syllabus_item(
        topic_id=topic_id,
        title="Advanced Topics",
        description=f"Advanced aspects of {topic_title}",
        parent_id=child1_id,
    )
    return [root_id, child1_id]
