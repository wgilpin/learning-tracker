"""create data_migrations tracking table

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-11
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS data_migrations (
            name        VARCHAR(255) PRIMARY KEY,
            applied_at  TIMESTAMPTZ NOT NULL
        )
    """)


def downgrade() -> None:
    op.drop_table("data_migrations")
