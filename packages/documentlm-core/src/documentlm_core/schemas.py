from __future__ import annotations

import uuid as _uuid_module
from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SyllabusStatus(StrEnum):
    UNRESEARCHED = "UNRESEARCHED"
    IN_PROGRESS = "IN_PROGRESS"
    MASTERED = "MASTERED"


class SourceStatus(StrEnum):
    QUEUED = "QUEUED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class SourceType(StrEnum):
    PDF_UPLOAD = "PDF_UPLOAD"
    URL_SCRAPE = "URL_SCRAPE"
    YOUTUBE_TRANSCRIPT = "YOUTUBE_TRANSCRIPT"
    RAW_TEXT = "RAW_TEXT"
    SEARCH = "SEARCH"


class IndexStatus(StrEnum):
    PENDING = "PENDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class CommentStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------


class TopicCreate(BaseModel):
    title: str
    description: str | None = None


class TopicRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# SyllabusItem
# ---------------------------------------------------------------------------


class SyllabusItemCreate(BaseModel):
    topic_id: UUID
    title: str
    description: str | None = None
    parent_id: UUID | None = None


class SyllabusItemRead(BaseModel):
    id: UUID
    topic_id: UUID
    parent_id: UUID | None
    title: str
    description: str | None
    status: SyllabusStatus

    model_config = {"from_attributes": True}


class SyllabusItemStatusUpdate(BaseModel):
    status: SyllabusStatus


class SyllabusItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class DescriptionGenerateRequest(BaseModel):
    title: str


class GeneratedDescriptionRead(BaseModel):
    description: str


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


class SourceCreate(BaseModel):
    topic_id: UUID
    url: str | None = None
    doi: str | None = None
    title: str
    authors: list[str]
    publication_date: date | None = None

    @model_validator(mode="after")
    def require_url_or_doi(self) -> SourceCreate:
        if not self.url and not self.doi:
            raise ValueError("At least one of url or doi must be provided")
        return self


class PrimarySourceCreate(BaseModel):
    topic_id: UUID
    source_type: SourceType
    title: str
    content: str
    url: str | None = None
    content_hash: str
    authors: list[str] = []


class SourceRead(BaseModel):
    id: UUID
    topic_id: UUID | None = None
    source_type: SourceType
    is_primary: bool
    index_status: IndexStatus
    index_error: str | None
    url: str | None
    doi: str | None
    title: str
    authors: list[str]
    publication_date: date | None
    verification_status: SourceStatus
    content: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------


class ChapterRead(BaseModel):
    id: UUID
    syllabus_item_id: UUID
    content: str
    sources: list[SourceRead]
    margin_comments: list[MarginCommentRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# MarginComment
# ---------------------------------------------------------------------------


class MarginCommentCreate(BaseModel):
    paragraph_anchor: str
    selected_text: str | None = None
    content: str


class MarginCommentRead(BaseModel):
    id: UUID
    chapter_id: UUID
    paragraph_anchor: str
    content: str
    response: str | None
    status: CommentStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Chat / Quiz (007-chat-agents-panel)
# ---------------------------------------------------------------------------


class QuizQuestion(BaseModel):
    text: str
    options: list[str]
    correct_index: int
    explanation: str


class QuizState(BaseModel):
    questions: list[QuizQuestion]
    user_responses: list[int | None]
    passed: bool | None
    generated_at: datetime


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    chapter_id: _uuid_module.UUID | None = None


class QuizResponseSubmit(BaseModel):
    question_index: int
    selected_option_index: int


class QuizAnswerResult(BaseModel):
    question_index: int
    is_correct: bool
    explanation: str
    quiz_passed: bool | None


# ---------------------------------------------------------------------------
# Illustrations (008-lesson-illustrations)
# ---------------------------------------------------------------------------


class ParagraphAssessment(BaseModel):
    requires_image: bool
    image_description: str
    image_caption: str = ""


class IllustrationRead(BaseModel):
    id: UUID
    chapter_id: UUID
    paragraph_index: int
    image_mime_type: str
    image_description: str
    image_caption: str
    created_at: datetime

    model_config = {"from_attributes": True}
