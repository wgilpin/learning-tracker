"""Integration tests for the manage CLI — invite, reset-password, deactivate-user."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from documentlm_core.db.models import InvitationCode, User

# ---------------------------------------------------------------------------
# The CLI subprocess connects to the same DB as the test suite.
# ---------------------------------------------------------------------------

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tracker:tracker@localhost:5432/tracker",
)

# subprocess env uses the synchronous-compatible URL format
_PROC_ENV = {**os.environ, "DATABASE_URL": TEST_DB_URL}


def _run_manage(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    """Run `uv run manage <args>` and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "api.cli", *args],
        capture_output=True,
        text=True,
        env=env or _PROC_ENV,
        cwd="/Users/will/projects/document-projects/learning-tracker",
    )


# ---------------------------------------------------------------------------
# A non-rollback session factory for CLI tests that need to read committed data.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def cli_engine():
    """Module-scoped engine that persists across tests (CLI commits its data)."""
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def cli_session(cli_engine) -> AsyncGenerator[AsyncSession, None]:
    """Plain session (no transaction wrap) so we can read CLI-committed rows."""
    factory = async_sessionmaker(bind=cli_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        # Clean up invitation_codes created in this test
        await session.execute(delete(InvitationCode))
        await session.commit()


# ---------------------------------------------------------------------------
# T007 — manage invite generates a valid code
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_invite_generates_code(cli_session: AsyncSession) -> None:
    # Clear any pre-existing codes so we can assert on exact count
    await cli_session.execute(delete(InvitationCode))
    await cli_session.commit()

    result = _run_manage("invite")

    assert result.returncode == 0, f"stderr: {result.stderr}"
    code = result.stdout.strip()
    assert re.fullmatch(r"INV-[0-9a-f]{60}", code), f"Unexpected code format: {code!r}"

    rows = (await cli_session.execute(select(InvitationCode))).scalars().all()
    assert len(rows) == 1
    assert rows[0].code == code
    assert rows[0].is_used is False


# ---------------------------------------------------------------------------
# T008 — two invocations produce two distinct codes
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_invite_each_call_unique(cli_session: AsyncSession) -> None:
    r1 = _run_manage("invite")
    r2 = _run_manage("invite")

    assert r1.returncode == 0
    assert r2.returncode == 0

    code1 = r1.stdout.strip()
    code2 = r2.stdout.strip()
    assert code1 != code2

    rows = (await cli_session.execute(select(InvitationCode))).scalars().all()
    codes_in_db = {row.code for row in rows}
    assert code1 in codes_in_db
    assert code2 in codes_in_db


# ---------------------------------------------------------------------------
# T009 — bad DATABASE_URL exits 1 with error on stderr
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_invite_db_error() -> None:
    bad_env = {**os.environ, "DATABASE_URL": "postgresql+asyncpg://bad:bad@localhost:9999/no"}
    result = _run_manage("invite", env=bad_env)

    assert result.returncode == 1
    assert "Error:" in result.stderr


# ---------------------------------------------------------------------------
# T014 — reset-password and deactivate-user
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def existing_user(cli_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Create a User row for CLI tests and clean it up afterwards."""
    from documentlm_core.auth import hash_password

    user = User(
        id=uuid.uuid4(),
        email="cli-test@example.com",
        password_hash=hash_password("original"),
        is_active=True,
    )
    cli_session.add(user)
    await cli_session.commit()
    await cli_session.refresh(user)
    yield user
    await cli_session.execute(delete(User).where(User.id == user.id))
    await cli_session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_reset_password_updates_hash(
    existing_user: User, cli_session: AsyncSession
) -> None:
    result = _run_manage("reset-password", existing_user.email, "newpassword123")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    await cli_session.refresh(existing_user)
    from documentlm_core.auth import verify_password

    assert verify_password("newpassword123", existing_user.password_hash)
    assert not verify_password("original", existing_user.password_hash)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_reset_password_unknown_email() -> None:
    result = _run_manage("reset-password", "nobody@nowhere.com", "pass")
    assert result.returncode == 1
    assert "Error:" in result.stderr


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_deactivate_user_sets_flag(
    existing_user: User, cli_session: AsyncSession
) -> None:
    result = _run_manage("deactivate-user", existing_user.email)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    await cli_session.refresh(existing_user)
    assert existing_user.is_active is False
    assert existing_user.deactivated_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_deactivate_user_unknown_email() -> None:
    result = _run_manage("deactivate-user", "nobody@nowhere.com")
    assert result.returncode == 1
    assert "Error:" in result.stderr


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_deactivate_already_deactivated(
    existing_user: User, cli_session: AsyncSession
) -> None:
    # Deactivate once (should succeed)
    r1 = _run_manage("deactivate-user", existing_user.email)
    assert r1.returncode == 0

    # Deactivate again (should fail with exit 1)
    r2 = _run_manage("deactivate-user", existing_user.email)
    assert r2.returncode == 1
    assert "Error:" in r2.stderr
