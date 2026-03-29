"""Unit tests for source service: deduplication logic and status transitions."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from documentlm_core.schemas import IndexStatus, SourceCreate, SourceRead, SourceStatus, SourceType


def _make_source_read(
    *,
    source_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    doi: str | None = "10.1234/test",
    url: str | None = None,
    verification_status: SourceStatus = SourceStatus.QUEUED,
) -> SourceRead:
    return SourceRead(
        id=source_id or uuid.uuid4(),
        topic_id=topic_id or uuid.uuid4(),
        source_type=SourceType.SEARCH,
        is_primary=False,
        index_status=IndexStatus.PENDING,
        index_error=None,
        url=url,
        doi=doi,
        title="Test Paper",
        authors=["Author A"],
        publication_date=None,
        verification_status=verification_status,
        content=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_source_deduplicates_by_doi() -> None:
    """create_source returns existing record when DOI already exists for topic."""
    from documentlm_core.services import source as source_svc

    topic_id = uuid.uuid4()
    existing = _make_source_read(topic_id=topic_id, doi="10.1234/dup")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock(
        id=existing.id,
        topic_id=topic_id,
        source_type="SEARCH",
        index_status="PENDING",
        index_error=None,
        url=None,
        doi="10.1234/dup",
        title="Test Paper",
        authors=["Author A"],
        publication_date=None,
        verification_status="QUEUED",
        content=None,
    )
    mock_session.execute = AsyncMock(return_value=mock_result)

    data = SourceCreate(
        topic_id=topic_id, doi="10.1234/dup", title="Test Paper", authors=["Author A"]
    )
    result = await source_svc.create_source(mock_session, data)

    assert result.id == existing.id
    # Should NOT have called session.add (duplicate detected before insert)
    mock_session.add.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_source_deduplicates_by_url() -> None:
    """create_source returns existing record when URL already exists for topic."""
    from documentlm_core.services import source as source_svc

    topic_id = uuid.uuid4()
    existing_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    # No DOI on this source, so only one execute: the URL check returning the match
    url_result = MagicMock()
    url_result.scalar_one_or_none.return_value = MagicMock(
        id=existing_id,
        topic_id=topic_id,
        source_type="SEARCH",
        index_status="PENDING",
        index_error=None,
        url="https://example.com/paper",
        doi=None,
        title="Test Paper",
        authors=["Author B"],
        publication_date=None,
        verification_status="QUEUED",
        content=None,
    )
    mock_session.execute = AsyncMock(return_value=url_result)

    data = SourceCreate(
        topic_id=topic_id, url="https://example.com/paper", title="Test Paper", authors=["Author B"]
    )
    result = await source_svc.create_source(mock_session, data)

    assert result.id == existing_id
    mock_session.add.assert_not_called()


@pytest.mark.unit
def test_source_create_requires_url_or_doi() -> None:
    """SourceCreate raises ValueError when neither url nor doi is provided."""
    with pytest.raises(ValueError, match="url or doi"):
        SourceCreate(topic_id=uuid.uuid4(), title="Bad Source", authors=[])


@pytest.mark.unit
def test_source_create_accepts_doi_only() -> None:
    sc = SourceCreate(topic_id=uuid.uuid4(), doi="10.1234/ok", title="OK", authors=[])
    assert sc.doi == "10.1234/ok"


@pytest.mark.unit
def test_source_create_accepts_url_only() -> None:
    sc = SourceCreate(topic_id=uuid.uuid4(), url="https://example.com", title="OK", authors=[])
    assert sc.url == "https://example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_source_sets_verified_status() -> None:
    from documentlm_core.services import source as source_svc

    source_id = uuid.uuid4()
    mock_orm = MagicMock()
    mock_orm.id = source_id
    mock_orm.topic_id = uuid.uuid4()
    mock_orm.source_type = "SEARCH"
    mock_orm.index_status = "PENDING"
    mock_orm.index_error = None
    mock_orm.url = None
    mock_orm.doi = "10.1234/x"
    mock_orm.title = "Paper"
    mock_orm.authors = []
    mock_orm.publication_date = None
    mock_orm.verification_status = "QUEUED"
    mock_orm.content = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_orm
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await source_svc.verify_source(mock_session, source_id)

    assert mock_orm.verification_status == "VERIFIED"
    assert result.verification_status == SourceStatus.VERIFIED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reject_source_sets_rejected_status() -> None:
    from documentlm_core.services import source as source_svc

    source_id = uuid.uuid4()
    mock_orm = MagicMock()
    mock_orm.id = source_id
    mock_orm.topic_id = uuid.uuid4()
    mock_orm.source_type = "SEARCH"
    mock_orm.index_status = "PENDING"
    mock_orm.index_error = None
    mock_orm.url = None
    mock_orm.doi = "10.1234/x"
    mock_orm.title = "Paper"
    mock_orm.authors = []
    mock_orm.publication_date = None
    mock_orm.verification_status = "QUEUED"
    mock_orm.content = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_orm
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await source_svc.reject_source(mock_session, source_id)

    assert mock_orm.verification_status == "REJECTED"
    assert result.verification_status == SourceStatus.REJECTED
