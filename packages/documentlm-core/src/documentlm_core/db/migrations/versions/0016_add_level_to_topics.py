"""add level column to topics

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE topics ADD COLUMN IF NOT EXISTS level VARCHAR(50) DEFAULT 'intermediate'"
    )


def downgrade() -> None:
    op.drop_column("topics", "level")
