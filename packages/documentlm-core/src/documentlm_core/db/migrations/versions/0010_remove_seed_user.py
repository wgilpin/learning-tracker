"""Remove seed user and all data owned by them.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    conn = op.get_bind()
    # CASCADE on topics.user_id and sources via user_source_refs handles cleanup
    conn.execute(
        sa.text("DELETE FROM users WHERE id = :id"),
        {"id": SEED_USER_ID},
    )


def downgrade() -> None:
    # Seed user is gone intentionally — no restoration on downgrade
    pass
