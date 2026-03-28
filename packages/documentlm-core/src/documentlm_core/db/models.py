from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    UUID as SQLUUID,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Topic  (T011)
# ---------------------------------------------------------------------------


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    syllabus_items: Mapped[list[SyllabusItem]] = relationship(
        "SyllabusItem", back_populates="topic", cascade="all, delete-orphan"
    )
    chapters: Mapped[list[AtomicChapter]] = relationship(
        "AtomicChapter", back_populates="topic", cascade="all, delete-orphan"
    )
    sources: Mapped[list[Source]] = relationship(
        "Source", back_populates="topic", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# SyllabusItem  (T012)
# ---------------------------------------------------------------------------


class SyllabusItem(Base):
    __tablename__ = "syllabus_items"

    id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("syllabus_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNRESEARCHED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    topic: Mapped[Topic] = relationship("Topic", back_populates="syllabus_items")
    chapter: Mapped[AtomicChapter | None] = relationship(
        "AtomicChapter", back_populates="syllabus_item", uselist=False
    )
    children: Mapped[list[SyllabusItem]] = relationship(
        "SyllabusItem",
        back_populates="parent",
        foreign_keys="SyllabusItem.parent_id",
    )
    parent: Mapped[SyllabusItem | None] = relationship(
        "SyllabusItem",
        back_populates="children",
        foreign_keys="SyllabusItem.parent_id",
        remote_side="SyllabusItem.id",
    )


# ---------------------------------------------------------------------------
# Source + ChapterSource  (T013)
# ---------------------------------------------------------------------------


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    publication_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("topic_id", "doi", name="uq_source_topic_doi"),
        UniqueConstraint("topic_id", "url", name="uq_source_topic_url"),
    )

    topic: Mapped[Topic] = relationship("Topic", back_populates="sources")
    chapter_sources: Mapped[list[ChapterSource]] = relationship(
        "ChapterSource", back_populates="source", cascade="all, delete-orphan"
    )


class ChapterSource(Base):
    __tablename__ = "chapter_sources"

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("atomic_chapters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )

    chapter: Mapped[AtomicChapter] = relationship("AtomicChapter", back_populates="chapter_sources")
    source: Mapped[Source] = relationship("Source", back_populates="chapter_sources")


# ---------------------------------------------------------------------------
# AtomicChapter + MarginComment  (T014)
# ---------------------------------------------------------------------------


class AtomicChapter(Base):
    __tablename__ = "atomic_chapters"

    id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    syllabus_item_id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("syllabus_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    topic: Mapped[Topic] = relationship("Topic", back_populates="chapters")
    syllabus_item: Mapped[SyllabusItem] = relationship("SyllabusItem", back_populates="chapter")
    margin_comments: Mapped[list[MarginComment]] = relationship(
        "MarginComment", back_populates="chapter", cascade="all, delete-orphan"
    )
    chapter_sources: Mapped[list[ChapterSource]] = relationship(
        "ChapterSource", back_populates="chapter", cascade="all, delete-orphan"
    )


class MarginComment(Base):
    __tablename__ = "margin_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("atomic_chapters.id", ondelete="CASCADE"),
        nullable=False,
    )
    paragraph_anchor: Mapped[str] = mapped_column(String(500), nullable=False)
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chapter: Mapped[AtomicChapter] = relationship("AtomicChapter", back_populates="margin_comments")

