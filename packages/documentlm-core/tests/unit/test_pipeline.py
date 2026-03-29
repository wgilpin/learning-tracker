"""Unit tests for services/pipeline.py — all HTTP and ChromaDB calls mocked."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from documentlm_core.schemas import IndexStatus, SourceType


def _make_source(
    *,
    source_type: str = SourceType.SEARCH,
    url: str | None = "https://example.com/paper",
    doi: str | None = None,
    content: str | None = None,
    index_status: str = IndexStatus.PENDING,
    topic_id: uuid.UUID | None = None,
) -> MagicMock:
    source = MagicMock()
    source.id = uuid.uuid4()
    source.topic_id = topic_id or uuid.uuid4()
    source.source_type = source_type
    source.url = url
    source.doi = doi
    source.content = content
    source.index_status = index_status
    source.index_error = None
    return source


def _make_session(source: MagicMock) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = source
    session.execute.return_value = result
    return session


@pytest.fixture()
def chroma_client_mock() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# Idempotency (US4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_already_indexed_source_returns_immediately() -> None:
    source = _make_source(index_status=IndexStatus.INDEXED)
    session = _make_session(source)

    with (
        patch("documentlm_core.services.pipeline.get_chroma_client") as mock_chroma,
        patch("documentlm_core.services.pipeline._fetch_url") as mock_fetch,
    ):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(source.id, session)

    mock_fetch.assert_not_called()
    mock_chroma.assert_not_called()
    assert source.index_status == IndexStatus.INDEXED  # unchanged


# ---------------------------------------------------------------------------
# SEARCH source with URL (US2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_source_with_url_fetches_and_indexes() -> None:
    source = _make_source(source_type=SourceType.SEARCH, url="https://example.com")
    session = _make_session(source)

    with (
        patch("documentlm_core.services.pipeline.get_chroma_client"),
        patch("documentlm_core.services.pipeline.upsert_source_chunks") as mock_upsert,
        patch(
            "documentlm_core.services.pipeline._fetch_url",
            new=AsyncMock(return_value="extracted text from url"),
        ),
        patch(
            "documentlm_core.services.pipeline._chunk",
            return_value=["chunk 0", "chunk 1"],
        ),
    ):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(source.id, session)

    mock_upsert.assert_called_once()
    assert source.index_status == IndexStatus.INDEXED
    assert source.index_error is None
    assert source.content == "extracted text from url"


# ---------------------------------------------------------------------------
# SEARCH DOI-only — FAILED (US2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_doi_only_marks_failed() -> None:
    source = _make_source(source_type=SourceType.SEARCH, url=None, doi="10.1234/paper")
    session = _make_session(source)

    with patch("documentlm_core.services.pipeline.get_chroma_client"):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(source.id, session)

    assert source.index_status == IndexStatus.FAILED
    assert "DOI-only" in (source.index_error or "")


# ---------------------------------------------------------------------------
# PDF_UPLOAD — uses stored content (US2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pdf_upload_uses_stored_content() -> None:
    source = _make_source(
        source_type=SourceType.PDF_UPLOAD,
        url=None,
        content="stored pdf text",
    )
    session = _make_session(source)

    with (
        patch("documentlm_core.services.pipeline.get_chroma_client"),
        patch("documentlm_core.services.pipeline.upsert_source_chunks"),
        patch("documentlm_core.services.pipeline._fetch_url") as mock_fetch,
        patch(
            "documentlm_core.services.pipeline._chunk",
            return_value=["chunk"],
        ),
    ):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(source.id, session)

    mock_fetch.assert_not_called()
    assert source.index_status == IndexStatus.INDEXED


# ---------------------------------------------------------------------------
# RAW_TEXT — uses stored content (US2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_text_uses_stored_content() -> None:
    source = _make_source(
        source_type=SourceType.RAW_TEXT,
        url=None,
        content="raw pasted text",
    )
    session = _make_session(source)

    with (
        patch("documentlm_core.services.pipeline.get_chroma_client"),
        patch("documentlm_core.services.pipeline.upsert_source_chunks"),
        patch("documentlm_core.services.pipeline._fetch_url") as mock_fetch,
        patch(
            "documentlm_core.services.pipeline._chunk",
            return_value=["chunk"],
        ),
    ):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(source.id, session)

    mock_fetch.assert_not_called()
    assert source.index_status == IndexStatus.INDEXED


# ---------------------------------------------------------------------------
# URL_SCRAPE — calls fetch_url (US2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_url_scrape_calls_fetch_url() -> None:
    source = _make_source(source_type=SourceType.URL_SCRAPE, url="https://example.com/article")
    session = _make_session(source)

    with (
        patch("documentlm_core.services.pipeline.get_chroma_client"),
        patch("documentlm_core.services.pipeline.upsert_source_chunks"),
        patch(
            "documentlm_core.services.pipeline._fetch_url",
            new=AsyncMock(return_value="scraped content"),
        ) as mock_fetch,
        patch("documentlm_core.services.pipeline._chunk", return_value=["chunk"]),
    ):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(source.id, session)

    mock_fetch.assert_called_once_with("https://example.com/article")
    assert source.index_status == IndexStatus.INDEXED


# ---------------------------------------------------------------------------
# YOUTUBE_TRANSCRIPT — calls fetch_youtube (US2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_youtube_calls_fetch_youtube() -> None:
    source = _make_source(
        source_type=SourceType.YOUTUBE_TRANSCRIPT,
        url="https://www.youtube.com/watch?v=abc123",
    )
    session = _make_session(source)

    with (
        patch("documentlm_core.services.pipeline.get_chroma_client"),
        patch("documentlm_core.services.pipeline.upsert_source_chunks"),
        patch(
            "documentlm_core.services.pipeline._fetch_youtube",
            new=AsyncMock(return_value="transcript text"),
        ) as mock_yt,
        patch("documentlm_core.services.pipeline._chunk", return_value=["chunk"]),
    ):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(source.id, session)

    mock_yt.assert_called_once_with("https://www.youtube.com/watch?v=abc123")
    assert source.index_status == IndexStatus.INDEXED


# ---------------------------------------------------------------------------
# Extraction failure — sets FAILED, does not raise (US2 / FR-006)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extraction_failure_sets_failed_does_not_raise() -> None:
    source = _make_source(source_type=SourceType.URL_SCRAPE, url="https://broken.example")
    session = _make_session(source)

    with (
        patch("documentlm_core.services.pipeline.get_chroma_client"),
        patch(
            "documentlm_core.services.pipeline._fetch_url",
            new=AsyncMock(side_effect=RuntimeError("connection refused")),
        ),
    ):
        from documentlm_core.services.pipeline import extract_and_index_source

        # Must NOT raise
        await extract_and_index_source(source.id, session)

    assert source.index_status == IndexStatus.FAILED
    assert "connection refused" in (source.index_error or "")


# ---------------------------------------------------------------------------
# Source not found — no-op, does not raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_source_is_noop() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    with patch("documentlm_core.services.pipeline.get_chroma_client"):
        from documentlm_core.services.pipeline import extract_and_index_source

        await extract_and_index_source(uuid.uuid4(), session)
    # No exception raised — test passes
