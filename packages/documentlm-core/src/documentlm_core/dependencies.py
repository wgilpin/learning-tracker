"""FastAPI dependencies for authentication."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.session import get_session


def get_current_user_id(request: Request) -> uuid.UUID:
    """Extract the authenticated user_id from the signed session cookie.

    Raises HTTP 401 if the session contains no user_id.
    """
    raw = request.session.get("user_id")
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return uuid.UUID(raw)


async def require_active_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Return the User ORM object for the current session.

    Raises HTTP 403 if the account is deactivated.
    """
    from documentlm_core.db.models import User

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")
    return user
