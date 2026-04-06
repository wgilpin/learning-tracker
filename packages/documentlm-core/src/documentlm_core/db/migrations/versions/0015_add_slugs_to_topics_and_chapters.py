"""add slug columns to topics and syllabus_items

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-06
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def _make_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "item"


def upgrade() -> None:
    bind = op.get_bind()

    # --- topics ----------------------------------------------------------
    op.execute("ALTER TABLE topics ADD COLUMN IF NOT EXISTS slug VARCHAR(500)")

    topics = bind.execute(sa.text("SELECT id, title FROM topics ORDER BY created_at")).fetchall()
    used_topic_slugs: set[str] = set()
    for topic_id, title in topics:
        base = _make_slug(title)
        slug = base
        counter = 2
        while slug in used_topic_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        used_topic_slugs.add(slug)
        bind.execute(
            sa.text("UPDATE topics SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": topic_id},
        )

    op.execute("ALTER TABLE topics ALTER COLUMN slug SET NOT NULL")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_topics_slug ON topics (slug)"
    )

    # --- syllabus_items --------------------------------------------------
    op.execute("ALTER TABLE syllabus_items ADD COLUMN IF NOT EXISTS slug VARCHAR(500)")

    items = bind.execute(
        sa.text("SELECT id, topic_id, title FROM syllabus_items ORDER BY created_at")
    ).fetchall()
    topic_slug_sets: dict[str, set[str]] = {}
    for item_id, topic_id, title in items:
        key = str(topic_id)
        if key not in topic_slug_sets:
            topic_slug_sets[key] = set()
        base = _make_slug(title)
        slug = base
        counter = 2
        while slug in topic_slug_sets[key]:
            slug = f"{base}-{counter}"
            counter += 1
        topic_slug_sets[key].add(slug)
        bind.execute(
            sa.text("UPDATE syllabus_items SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": item_id},
        )

    op.execute("ALTER TABLE syllabus_items ALTER COLUMN slug SET NOT NULL")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_syllabus_item_topic_slug "
        "ON syllabus_items (topic_id, slug)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_syllabus_item_topic_slug")
    op.execute("DROP INDEX IF EXISTS uq_topics_slug")
    op.drop_column("syllabus_items", "slug")
    op.drop_column("topics", "slug")
