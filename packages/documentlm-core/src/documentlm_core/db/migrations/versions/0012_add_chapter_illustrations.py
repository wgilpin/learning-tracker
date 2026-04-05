"""Add chapter_illustrations table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapter_illustrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paragraph_index", sa.Integer(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("image_mime_type", sa.String(length=64), nullable=False),
        sa.Column("image_description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["atomic_chapters.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chapter_id", "paragraph_index", name="uq_chapter_illustration"
        ),
    )


def downgrade() -> None:
    op.drop_table("chapter_illustrations")
