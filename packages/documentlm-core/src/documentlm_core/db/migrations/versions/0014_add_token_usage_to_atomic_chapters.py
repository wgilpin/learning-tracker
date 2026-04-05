"""add token usage columns to atomic_chapters

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE atomic_chapters ADD COLUMN IF NOT EXISTS generation_input_tokens INTEGER"
    )
    op.execute(
        "ALTER TABLE atomic_chapters ADD COLUMN IF NOT EXISTS generation_output_tokens INTEGER"
    )
    op.execute(
        "ALTER TABLE atomic_chapters ADD COLUMN IF NOT EXISTS generation_image_count INTEGER"
    )


def downgrade() -> None:
    op.drop_column("atomic_chapters", "generation_image_count")
    op.drop_column("atomic_chapters", "generation_output_tokens")
    op.drop_column("atomic_chapters", "generation_input_tokens")
