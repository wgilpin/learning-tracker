"""Make topics.user_id NOT NULL.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-31
"""

from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("topics", "user_id", nullable=False)


def downgrade() -> None:
    op.alter_column("topics", "user_id", nullable=True)
