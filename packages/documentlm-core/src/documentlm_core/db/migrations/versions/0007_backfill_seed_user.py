"""Create seed user and backfill topics.user_id.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    conn = op.get_bind()

    # Backfill any topics with no user_id — assigns to seed user as a placeholder.
    # Migration 0010 removes the seed user; topics owned by it are deleted by CASCADE.
    conn.execute(
        sa.text("UPDATE topics SET user_id = :uid WHERE user_id IS NULL"),
        {"uid": SEED_USER_ID},
    )


def downgrade() -> None:
    # No-op: seed user and backfilled rows stay; NOT NULL will be re-applied
    # by 0008 and removed by 0008 downgrade if needed.
    pass
