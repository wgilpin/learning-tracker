"""Password hashing and verification using bcrypt."""

from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password* (cost=12)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches *hashed*."""
    return bcrypt.checkpw(password.encode(), hashed.encode())
