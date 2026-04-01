"""Bibliography service: verified sources for a topic."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Source, UserSourceRef
from documentlm_core.schemas import SourceRead

logger = logging.getLogger(__name__)


async def get_bibliography(
    session: AsyncSession,
    topic_id: uuid.UUID,
) -> list[SourceRead]:
    result = await session.execute(
        select(Source)
        .join(UserSourceRef, UserSourceRef.source_id == Source.id)
        .where(UserSourceRef.topic_id == topic_id)
        .order_by(UserSourceRef.created_at)
    )
    return [SourceRead.model_validate(s) for s in result.scalars().all()]
