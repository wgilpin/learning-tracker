"""Add nullable user_id FK to topics.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("topics_user_id_idx", "topics", ["user_id"])


def downgrade() -> None:
    op.drop_index("topics_user_id_idx", table_name="topics")
    op.drop_column("topics", "user_id")
