"""Integration tests for source deduplication with reference counting (US4).

Tests are written FIRST (TDD). They must FAIL until T037-T041 are implemented.
"""

from __future__ import annotations

import json
import uuid
from base64 import b64encode

import chromadb
import itsdangerous
import pytest
import pytest_asyncio
from documentlm_core.config import settings
from documentlm_core.db.session import get_session
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _make_session_cookie(user_id: uuid.UUID) -> str:
    signer = itsdangerous.TimestampSigner(settings.session_secret_key)
    payload = b64encode(json.dumps({"user_id": str(user_id)}).encode()).decode()
    return signer.sign(payload).decode()


@pytest_asyncio.fixture
async def user_b(async_session: AsyncSession):
    from documentlm_core.auth import hash_password
    from documentlm_core.db.models import User

    user = User(
        id=uuid.uuid4(),
        email="dedup_user_b@example.com",
        password_hash=hash_password("password_b"),
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest_asyncio.fixture
async def topic_a(async_session: AsyncSession, test_user):
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    return await create_topic(async_session, TopicCreate(title="User A Topic"), user_id=test_user.id)


@pytest_asyncio.fixture
async def topic_b(async_session: AsyncSession, user_b):
    from documentlm_core.schemas import TopicCreate
    from documentlm_core.services.topic import create_topic

    return await create_topic(async_session, TopicCreate(title="User B Topic"), user_id=user_b.id)


# ---------------------------------------------------------------------------
# T034 — Deduplication: same content → one Source, two UserSourceRefs
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_dedup_shared_storage(
    async_session: AsyncSession,
    test_user,
    user_b,
    topic_a,
    topic_b,
) -> None:
    """Uploading the same content as two users creates one Source, two UserSourceRefs."""
    from documentlm_core.db.models import Source, UserSourceRef
    from documentlm_core.services.source import add_source_for_user, compute_content_hash

    content = "Shared document content about machine learning"
    content_hash = compute_content_hash(content)

    # User A uploads
    source_a, ref_a, dup_a = await add_source_for_user(
        async_session,
        user_id=test_user.id,
        topic_id=topic_a.id,
        title="ML Paper",
        content=content,
        content_hash=content_hash,
    )
    assert not dup_a

    # User B uploads same content
    source_b, ref_b, dup_b = await add_source_for_user(
        async_session,
        user_id=user_b.id,
        topic_id=topic_b.id,
        title="ML Paper",
        content=content,
        content_hash=content_hash,
    )
    assert dup_b  # was a duplicate

    # Same source row
    assert source_a.id == source_b.id

    # Exactly one sources row
    source_count = await async_session.scalar(
        select(func.count(Source.id)).where(Source.id == source_a.id)
    )
    assert source_count == 1

    # Two UserSourceRef rows
    ref_count = await async_session.scalar(
        select(func.count(UserSourceRef.id)).where(UserSourceRef.source_id == source_a.id)
    )
    assert ref_count == 2


# ---------------------------------------------------------------------------
# T035 — Ref-count delete: partial then full removal
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_ref_count_delete(
    async_session: AsyncSession,
    test_user,
    user_b,
    topic_a,
    topic_b,
) -> None:
    """Deleting user A's ref keeps the Source; deleting user B's ref removes it."""
    from unittest.mock import MagicMock, patch

    from documentlm_core.db.models import Source, UserSourceRef
    from documentlm_core.services.source import add_source_for_user, compute_content_hash, delete_source_for_user

    content = "Ref-count test content"
    content_hash = compute_content_hash(content)

    source_a, _, _ = await add_source_for_user(
        async_session, user_id=test_user.id, topic_id=topic_a.id,
        title="Ref Test", content=content, content_hash=content_hash,
    )
    await add_source_for_user(
        async_session, user_id=user_b.id, topic_id=topic_b.id,
        title="Ref Test", content=content, content_hash=content_hash,
    )

    ephemeral = chromadb.EphemeralClient()

    # User A deletes — source should still exist (ref_count=1 remaining)
    with patch(
        "documentlm_core.services.source.get_chroma_client", return_value=ephemeral
    ):
        source_deleted = await delete_source_for_user(
            async_session, user_id=test_user.id, source_id=source_a.id, topic_id=topic_a.id,
        )
    assert not source_deleted  # source row still exists

    remaining_refs = await async_session.scalar(
        select(func.count(UserSourceRef.id)).where(UserSourceRef.source_id == source_a.id)
    )
    assert remaining_refs == 1

    source_still_exists = await async_session.scalar(
        select(func.count(Source.id)).where(Source.id == source_a.id)
    )
    assert source_still_exists == 1

    # User B deletes — source should be gone (ref_count=0)
    with patch(
        "documentlm_core.services.source.get_chroma_client", return_value=ephemeral
    ):
        source_deleted = await delete_source_for_user(
            async_session, user_id=user_b.id, source_id=source_a.id, topic_id=topic_b.id,
        )
    assert source_deleted  # source row gone

    source_gone = await async_session.scalar(
        select(func.count(Source.id)).where(Source.id == source_a.id)
    )
    assert source_gone == 0


# ---------------------------------------------------------------------------
# T036 — Query after partial delete: user B still sees chunks
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_query_after_partial_delete(
    async_session: AsyncSession,
    test_user,
    user_b,
    topic_a,
    topic_b,
) -> None:
    """After user A deletes shared source, user B's chunks still exist."""
    from unittest.mock import patch

    from documentlm_core.services.chroma import query_topic_chunks_with_sources, upsert_source_chunks
    from documentlm_core.services.source import add_source_for_user, compute_content_hash, delete_source_for_user

    content = "Neural networks learn representations"
    content_hash = compute_content_hash(content)

    source, _, _ = await add_source_for_user(
        async_session, user_id=test_user.id, topic_id=topic_a.id,
        title="NN Paper", content=content, content_hash=content_hash,
    )
    await add_source_for_user(
        async_session, user_id=user_b.id, topic_id=topic_b.id,
        title="NN Paper", content=content, content_hash=content_hash,
    )

    ephemeral = chromadb.EphemeralClient()
    upsert_source_chunks(ephemeral, source.id, [content])

    # User A deletes their ref
    with patch("documentlm_core.services.source.get_chroma_client", return_value=ephemeral):
        await delete_source_for_user(
            async_session, user_id=test_user.id, source_id=source.id, topic_id=topic_a.id,
        )

    # User B can still query (source and collection still exist)
    chunks = query_topic_chunks_with_sources(ephemeral, [source.id], "neural networks", n_results=5)
    assert len(chunks) >= 1
