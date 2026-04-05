"""add image_caption to chapter_illustrations

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapter_illustrations",
        sa.Column("image_caption", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("chapter_illustrations", "image_caption")
