"""Bibliography service: verified sources for a topic."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Source
from documentlm_core.schemas import SourceRead

logger = logging.getLogger(__name__)


async def get_bibliography(
    session: AsyncSession,
    topic_id: uuid.UUID,
) -> list[SourceRead]:
    result = await session.execute(
        select(Source).where(Source.topic_id == topic_id)
    )
    return [SourceRead.model_validate(s) for s in result.scalars().all()]
