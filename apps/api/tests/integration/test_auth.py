"""Integration tests for registration, login, and logout flows."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from documentlm_core.db.models import InvitationCode, User
from documentlm_core.services.invitation import create_invitation_code


# ---------------------------------------------------------------------------
# Helper: create an invitation code inside the test transaction
# ---------------------------------------------------------------------------


async def _make_code(session: AsyncSession) -> str:
    return await create_invitation_code(session)


# ---------------------------------------------------------------------------
# T012 — register_* tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_valid_code_creates_user_and_redirects(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    code = await _make_code(async_session)
    await async_session.commit()

    resp = await unauth_client.post(
        "/register",
        data={
            "invite_code": code,
            "email": "newuser@example.com",
            "password": "securepass1",
            "password_confirm": "securepass1",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303), resp.text
    # HTMX redirect or standard redirect
    assert resp.headers.get("HX-Redirect") == "/" or resp.headers.get("location") == "/"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_used_code_rejected(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    from documentlm_core.auth import hash_password

    # Pre-use the code
    code = await _make_code(async_session)
    user = User(
        id=uuid.uuid4(),
        email="used@example.com",
        password_hash=hash_password("x"),
    )
    async_session.add(user)
    inv = (await async_session.get(InvitationCode, code))
    assert inv is not None
    inv.is_used = True
    inv.used_by_user_id = user.id
    await async_session.commit()

    resp = await unauth_client.post(
        "/register",
        data={
            "invite_code": code,
            "email": "another@example.com",
            "password": "securepass1",
            "password_confirm": "securepass1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_invalid_code_rejected(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    resp = await unauth_client.post(
        "/register",
        data={
            "invite_code": "INVALID-CODE",
            "email": "x@example.com",
            "password": "securepass1",
            "password_confirm": "securepass1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    from documentlm_core.auth import hash_password

    user = User(
        id=uuid.uuid4(),
        email="dup@example.com",
        password_hash=hash_password("x"),
    )
    async_session.add(user)
    code = await _make_code(async_session)
    await async_session.commit()

    resp = await unauth_client.post(
        "/register",
        data={
            "invite_code": code,
            "email": "dup@example.com",
            "password": "securepass1",
            "password_confirm": "securepass1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_password_mismatch_rejected(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    code = await _make_code(async_session)
    await async_session.commit()

    resp = await unauth_client.post(
        "/register",
        data={
            "invite_code": code,
            "email": "mismatch@example.com",
            "password": "securepass1",
            "password_confirm": "different",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# T013 — login_* tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_correct_credentials_sets_session(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    from documentlm_core.auth import hash_password

    user = User(
        id=uuid.uuid4(),
        email="login@example.com",
        password_hash=hash_password("mypassword"),
    )
    async_session.add(user)
    await async_session.commit()

    resp = await unauth_client.post(
        "/login",
        data={"email": "login@example.com", "password": "mypassword"},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302, 303)
    assert resp.headers.get("HX-Redirect") == "/" or resp.headers.get("location") == "/"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    from documentlm_core.auth import hash_password

    user = User(
        id=uuid.uuid4(),
        email="wrongpw@example.com",
        password_hash=hash_password("correct"),
    )
    async_session.add(user)
    await async_session.commit()

    resp = await unauth_client.post(
        "/login",
        data={"email": "wrongpw@example.com", "password": "incorrect"},
        follow_redirects=False,
    )
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_deactivated_user_returns_403(
    unauth_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    from datetime import UTC, datetime

    from documentlm_core.auth import hash_password

    user = User(
        id=uuid.uuid4(),
        email="deactivated@example.com",
        password_hash=hash_password("pass"),
        is_active=False,
        deactivated_at=datetime.now(UTC),
    )
    async_session.add(user)
    await async_session.commit()

    resp = await unauth_client.post(
        "/login",
        data={"email": "deactivated@example.com", "password": "pass"},
        follow_redirects=False,
    )
    assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthenticated_access_redirects_to_login(
    unauth_client: AsyncClient,
) -> None:
    resp = await unauth_client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 303, 200)
    location = resp.headers.get("location", "") or resp.headers.get("HX-Redirect", "")
    assert "/login" in location
