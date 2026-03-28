"""Initial schema: all tables + pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-03-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "topics",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "syllabus_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("syllabus_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="UNRESEARCHED"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("authors", sa.JSON, nullable=False),
        sa.Column("publication_date", sa.Date, nullable=True),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("topic_id", "doi", name="uq_source_topic_doi"),
        sa.UniqueConstraint("topic_id", "url", name="uq_source_topic_url"),
    )

    op.create_table(
        "atomic_chapters",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "syllabus_item_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("syllabus_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "chapter_sources",
        sa.Column(
            "chapter_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("atomic_chapters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "margin_comments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("atomic_chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("paragraph_anchor", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )



def downgrade() -> None:
    op.drop_table("margin_comments")
    op.drop_table("chapter_sources")
    op.drop_table("atomic_chapters")
    op.drop_table("sources")
    op.drop_table("syllabus_items")
    op.drop_table("topics")
    op.execute("DROP EXTENSION IF EXISTS vector")
