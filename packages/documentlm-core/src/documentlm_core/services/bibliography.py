"""Bibliography service: verified sources for a topic."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import Source
from documentlm_core.schemas import SourceRead, SourceStatus

logger = logging.getLogger(__name__)


async def get_bibliography(
    session: AsyncSession,
    topic_id: uuid.UUID,
) -> list[SourceRead]:
    result = await session.execute(
        select(Source).where(
            Source.topic_id == topic_id,
            Source.verification_status == SourceStatus.VERIFIED.value,
        )
    )
    return [
        SourceRead(
            id=s.id,
            topic_id=s.topic_id,
            url=s.url,
            doi=s.doi,
            title=s.title,
            authors=list(s.authors),
            publication_date=s.publication_date,
            verification_status=SourceStatus(s.verification_status),
        )
        for s in result.scalars().all()
    ]
