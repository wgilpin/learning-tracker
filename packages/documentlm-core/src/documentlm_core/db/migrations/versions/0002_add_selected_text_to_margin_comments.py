"""add selected_text to margin_comments

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "margin_comments",
        sa.Column("selected_text", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("margin_comments", "selected_text")
