"""Invitation code service: generate and consume single-use codes."""

from __future__ import annotations

import secrets
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import InvitationCode

logger = logging.getLogger(__name__)


async def create_invitation_code(session: AsyncSession) -> str:
    """Generate a unique single-use invitation code, persist it, and return it.

    The code format is ``INV-<64-hex-chars>`` (32 random bytes, hex-encoded).
    """
    raw = secrets.token_hex(30)  # 60 hex chars + "INV-" prefix = 64 chars total
    code = f"INV-{raw}"
    record = InvitationCode(code=code)
    session.add(record)
    await session.commit()
    logger.info("Invitation code created code=%s", code)
    return code
