"""Add quiz columns to atomic_chapters.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "atomic_chapters",
        sa.Column("quiz_questions", sa.JSON(), nullable=True),
    )
    op.add_column(
        "atomic_chapters",
        sa.Column("quiz_user_responses", sa.JSON(), nullable=True),
    )
    op.add_column(
        "atomic_chapters",
        sa.Column("quiz_passed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "atomic_chapters",
        sa.Column("quiz_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("atomic_chapters", "quiz_generated_at")
    op.drop_column("atomic_chapters", "quiz_passed")
    op.drop_column("atomic_chapters", "quiz_user_responses")
    op.drop_column("atomic_chapters", "quiz_questions")
