"""Create user_source_refs, drop topic_id from sources, add global content_hash unique.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create user_source_refs table
    op.create_table(
        "user_source_refs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("user_id", "source_id", "topic_id", name="uq_user_source_ref"),
    )
    op.create_index("user_source_refs_source_id_idx", "user_source_refs", ["source_id"])
    op.create_index("user_source_refs_topic_id_idx", "user_source_refs", ["topic_id"])

    # 2. Backfill: one ref per existing source row using the topic's owner
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO user_source_refs (id, user_id, source_id, topic_id, created_at)
            SELECT
                gen_random_uuid(),
                t.user_id,
                s.id,
                s.topic_id,
                NOW()
            FROM sources s
            JOIN topics t ON t.id = s.topic_id
            ON CONFLICT (user_id, source_id, topic_id) DO NOTHING
            """
        )
    )

    # 3. Drop unique constraints that reference topic_id
    op.drop_constraint("uq_source_topic_doi", "sources", type_="unique")
    op.drop_constraint("uq_source_topic_url", "sources", type_="unique")
    op.drop_constraint("uq_source_topic_content_hash", "sources", type_="unique")

    # 4. Drop topic_id FK constraint and column from sources
    # (PostgreSQL auto-names the FK constraint; use drop_constraint with unique name)
    # Find and drop FK constraint on sources.topic_id
    conn.execute(
        sa.text(
            """
            DO $$
            DECLARE
                conname text;
            BEGIN
                SELECT tc.constraint_name INTO conname
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'sources'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND kcu.column_name = 'topic_id';
                IF conname IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE sources DROP CONSTRAINT ' || quote_ident(conname);
                END IF;
            END $$;
            """
        )
    )
    op.drop_column("sources", "topic_id")

    # 5. Add global UNIQUE index on content_hash (partial: only non-null)
    op.create_index(
        "uq_source_content_hash",
        "sources",
        ["content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    # Add topic_id back as nullable (cannot restore values without data)
    op.add_column(
        "sources",
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    # Re-add old constraints
    op.create_unique_constraint(
        "uq_source_topic_content_hash", "sources", ["topic_id", "content_hash"]
    )
    op.create_unique_constraint("uq_source_topic_doi", "sources", ["topic_id", "doi"])
    op.create_unique_constraint("uq_source_topic_url", "sources", ["topic_id", "url"])

    # Drop new content_hash index
    op.drop_index("uq_source_content_hash", table_name="sources")

    # Drop user_source_refs
    op.drop_index("user_source_refs_topic_id_idx", table_name="user_source_refs")
    op.drop_index("user_source_refs_source_id_idx", table_name="user_source_refs")
    op.drop_table("user_source_refs")
