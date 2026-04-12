"""add learning_objectives and objectives_mastered columns to syllabus_items

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-11
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE syllabus_items ADD COLUMN IF NOT EXISTS learning_objectives JSONB"
    )
    op.execute(
        "ALTER TABLE syllabus_items ADD COLUMN IF NOT EXISTS objectives_mastered JSONB"
    )


def downgrade() -> None:
    op.drop_column("syllabus_items", "objectives_mastered")
    op.drop_column("syllabus_items", "learning_objectives")
