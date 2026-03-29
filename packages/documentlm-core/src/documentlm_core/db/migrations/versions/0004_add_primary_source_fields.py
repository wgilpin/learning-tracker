"""add is_primary, content_hash to sources

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("sources", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_source_topic_content_hash", "sources", ["topic_id", "content_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_source_topic_content_hash", "sources", type_="unique")
    op.drop_column("sources", "content_hash")
    op.drop_column("sources", "is_primary")
