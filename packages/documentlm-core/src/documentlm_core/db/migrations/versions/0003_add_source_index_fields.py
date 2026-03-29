"""add source_type, index_status, index_error, content to sources

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("source_type", sa.String(20), nullable=False, server_default="SEARCH"),
    )
    op.add_column(
        "sources",
        sa.Column("index_status", sa.String(10), nullable=False, server_default="PENDING"),
    )
    op.add_column("sources", sa.Column("index_error", sa.Text, nullable=True))
    op.add_column("sources", sa.Column("content", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "content")
    op.drop_column("sources", "index_error")
    op.drop_column("sources", "index_status")
    op.drop_column("sources", "source_type")
