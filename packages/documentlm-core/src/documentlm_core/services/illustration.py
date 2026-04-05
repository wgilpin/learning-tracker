"""Illustration service: orchestrates section assessment, image generation, and persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.agents.illustration_assessor import assess_paragraph
from documentlm_core.agents.image_generator import generate_image
from documentlm_core.config import settings
from documentlm_core.db.models import ChapterIllustration
from documentlm_core.schemas import IllustrationRead

logger = logging.getLogger(__name__)


def _split_into_sections(content: str) -> list[tuple[int, str, str]]:
    """Split markdown content into ## sections for illustration assessment.

    Identifies each ## heading and gathers all subsequent \n\n-separated
    paragraphs as that section's body. Returns a list of:
        (paragraph_index, section_title, section_body)

    paragraph_index is the 1-based index of the ## heading paragraph in the
    \n\n split — this matches loop.index in the Jinja2 templates so the
    image is placed directly after the correct heading block.

    Content before the first ## heading is skipped (no semantic anchor).
    """
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    sections: list[tuple[int, str, str]] = []
    current_start: int | None = None
    current_title: str = ""
    current_body_parts: list[str] = []

    for i, para in enumerate(paragraphs, start=1):
        first_line = para.strip().splitlines()[0] if para.strip() else ""
        if first_line.startswith("## "):
            # Flush previous section before starting a new one
            if current_start is not None:
                body = "\n\n".join(p for p in current_body_parts if p).strip()
                sections.append((current_start, current_title, body))
            current_title = first_line.lstrip("# ").strip()
            # Inline body: any lines after the heading within this same para
            lines = para.strip().splitlines()
            inline_body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            current_body_parts = [inline_body] if inline_body else []
            current_start = i
        else:
            if current_start is not None:
                current_body_parts.append(para.strip())

    # Flush last section
    if current_start is not None:
        body = "\n\n".join(p for p in current_body_parts if p).strip()
        sections.append((current_start, current_title, body))

    return sections


async def run_illustration_pipeline(
    chapter_id: uuid.UUID,
    content: str,
    session: AsyncSession,
) -> None:
    """Assess each ## section and generate + persist illustrations where needed.

    Splits chapter content into ## heading sections. Each section (heading +
    body) is assessed as a semantic unit — larger chunks produce better image
    descriptions than individual \n\n paragraphs. The paragraph_index stored
    per illustration is the 1-based index of the ## paragraph in the \n\n
    split, matching loop.index in Jinja2 templates.

    Per-section failures are logged and skipped — the pipeline always runs to
    completion and never raises.

    Args:
        chapter_id: UUID of the AtomicChapter to illustrate.
        content: Full markdown chapter content.
        session: Active async SQLAlchemy session for DB writes.
    """
    sections = _split_into_sections(content)
    total = len(sections)
    logger.info(
        "IllustrationPipeline: starting chapter_id=%s sections=%d model=%r",
        chapter_id,
        total,
        settings.illustration_model,
    )

    generated = 0
    for para_index, title, body in sections:
        try:
            assessment = await assess_paragraph(title, body)
        except Exception:
            logger.exception(
                "IllustrationPipeline: assessment failed chapter_id=%s section=%d %r",
                chapter_id,
                para_index,
                title[:60],
            )
            continue

        if not assessment.requires_image:
            logger.debug(
                "IllustrationPipeline: section %d %r does not require image",
                para_index,
                title[:60],
            )
            continue

        try:
            result = await generate_image(
                assessment.image_description, settings.illustration_model
            )
        except Exception:
            logger.exception(
                "IllustrationPipeline: generation failed chapter_id=%s section=%d %r",
                chapter_id,
                para_index,
                title[:60],
            )
            continue

        if result is None:
            logger.warning(
                "IllustrationPipeline: generator returned None chapter_id=%s section=%d %r",
                chapter_id,
                para_index,
                title[:60],
            )
            continue

        image_bytes, mime_type = result
        illustration = ChapterIllustration(
            id=uuid.uuid4(),
            chapter_id=chapter_id,
            paragraph_index=para_index,
            image_data=image_bytes,
            image_mime_type=mime_type,
            image_description=assessment.image_description,
            created_at=datetime.now(UTC),
        )
        session.add(illustration)
        try:
            await session.flush()
            generated += 1
            logger.info(
                "IllustrationPipeline: persisted illustration chapter_id=%s"
                " section=%d bytes=%d",
                chapter_id,
                para_index,
                len(image_bytes),
            )
        except Exception:
            logger.exception(
                "IllustrationPipeline: DB write failed chapter_id=%s section=%d",
                chapter_id,
                para_index,
            )
            await session.rollback()

    logger.info(
        "IllustrationPipeline: complete chapter_id=%s sections=%d generated=%d",
        chapter_id,
        total,
        generated,
    )


async def get_illustrations(
    session: AsyncSession,
    chapter_id: uuid.UUID,
) -> dict[int, IllustrationRead]:
    """Fetch all illustrations for a chapter as a dict keyed by paragraph_index.

    Args:
        session: Active async SQLAlchemy session.
        chapter_id: UUID of the AtomicChapter.

    Returns:
        Mapping from paragraph_index (1-based int) to IllustrationRead.
        Empty dict if no illustrations exist.
    """
    result = await session.execute(
        select(ChapterIllustration).where(
            ChapterIllustration.chapter_id == chapter_id
        )
    )
    rows = result.scalars().all()
    return {row.paragraph_index: IllustrationRead.model_validate(row) for row in rows}
