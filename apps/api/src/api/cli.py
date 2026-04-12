"""Operator management CLI.

Usage (from repo root):
    uv run manage invite
    uv run manage reset-password user@example.com <new-password>
    uv run manage deactivate-user user@example.com
    uv run manage migrate-data [--list] [--run NAME]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subcommand: invite
# ---------------------------------------------------------------------------


async def _invite() -> None:
    from documentlm_core.db.session import AsyncSessionFactory
    from documentlm_core.services.invitation import create_invitation_code

    async with AsyncSessionFactory() as session:
        code = await create_invitation_code(session)
    print(code)


# ---------------------------------------------------------------------------
# Subcommand: reset-password
# ---------------------------------------------------------------------------


async def _reset_password(email: str, new_password: str) -> None:
    from sqlalchemy import select

    from documentlm_core.auth import hash_password
    from documentlm_core.db.models import User
    from documentlm_core.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"No user found with email {email!r}")
        user.password_hash = hash_password(new_password)
        await session.commit()
    print(f"Password updated for {email}")


# ---------------------------------------------------------------------------
# Subcommand: deactivate-user
# ---------------------------------------------------------------------------


async def _deactivate_user(email: str) -> None:
    from datetime import UTC, datetime

    from sqlalchemy import select

    from documentlm_core.db.models import User
    from documentlm_core.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"No user found with email {email!r}")
        if not user.is_active:
            raise ValueError(f"User {email!r} is already deactivated")
        user.is_active = False
        user.deactivated_at = datetime.now(UTC)
        await session.commit()
    print(f"User {email} deactivated.")


# ---------------------------------------------------------------------------
# Subcommand: migrate-data
# ---------------------------------------------------------------------------


async def _migrate_data(list_only: bool, run_name: str | None) -> None:
    from documentlm_core.data_migration_runner import list_migrations, run_migrations

    if list_only:
        list_migrations()
        return

    from documentlm_core.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        await run_migrations(session, name=run_name)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    parser = argparse.ArgumentParser(
        prog="manage",
        description="Learning Tracker operator CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("invite", help="Generate a single-use invitation code")

    rp = subparsers.add_parser("reset-password", help="Set a new password for a user account")
    rp.add_argument("email", help="Email address of the target user")
    rp.add_argument("new_password", metavar="new-password", help="Plaintext new password")

    du = subparsers.add_parser("deactivate-user", help="Deactivate a user account")
    du.add_argument("email", help="Email of the user to deactivate")

    md = subparsers.add_parser(
        "migrate-data",
        help="Run pending data migrations (backfills, AI-generated content, etc.)",
    )
    md.add_argument(
        "--list", action="store_true", dest="list_only",
        help="List all migrations with their applied/pending status",
    )
    md.add_argument(
        "--run", metavar="NAME", dest="run_name", default=None,
        help="Run a specific migration by name (e.g. 001_backfill_learning_objectives)",
    )

    args = parser.parse_args()

    if args.command == "invite":
        try:
            asyncio.run(_invite())
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            logger.exception("invite failed")
            sys.exit(1)

    elif args.command == "reset-password":
        try:
            asyncio.run(_reset_password(args.email, args.new_password))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            logger.exception("reset-password failed")
            sys.exit(1)

    elif args.command == "deactivate-user":
        try:
            asyncio.run(_deactivate_user(args.email))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            logger.exception("deactivate-user failed")
            sys.exit(1)

    elif args.command == "migrate-data":
        try:
            asyncio.run(_migrate_data(args.list_only, args.run_name))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            logger.exception("migrate-data failed")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
