"""User service: registration via invite, authentication, lookup."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.auth import hash_password, verify_password
from documentlm_core.db.models import InvitationCode, User

logger = logging.getLogger(__name__)


async def create_user_from_invite(
    session: AsyncSession,
    *,
    invite_code: str,
    email: str,
    password: str,
) -> User:
    """Register a new user consuming a single-use invitation code.

    Raises:
        ValueError: if the code is invalid/used, the email is duplicate,
                    or any other domain rule is violated.
    """
    inv = await session.get(InvitationCode, invite_code)
    if inv is None or inv.is_used:
        raise ValueError("Invalid or already-used invitation code")

    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
    )
    session.add(user)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Email {email!r} is already registered")

    inv.is_used = True
    inv.used_at = datetime.now(UTC)
    inv.used_by_user_id = user.id

    await session.commit()
    logger.info("User registered email=%s", email)
    return user


async def authenticate_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    """Verify credentials and return the User.

    Raises:
        ValueError: with a code hint for the caller to map to HTTP status.
            "not_found"        → 401
            "wrong_password"   → 401
            "deactivated"      → 403
    """
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("not_found")
    if not verify_password(password, user.password_hash):
        raise ValueError("wrong_password")
    if not user.is_active:
        raise ValueError("deactivated")
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
