# Implementation Plan: Multi-User Isolation

**Branch**: `004-multi-user-isolation` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-multi-user-isolation/spec.md`

## Summary

Add invitation-only multi-user support to the learning tracker. Each user owns their own courses, topics, content, and progress. Source documents are stored once globally (deduplicated by SHA-256 content hash) and referenced per-user via a join table with reference counting. A single `manage` CLI entry-point provides operator commands: generate invite codes, reset passwords, and deactivate accounts. Authentication uses Starlette's signed-cookie session middleware; no JS framework changes required.

## Technical Context

**Language/Version**: Python 3.12 (uv workspaces)
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, HTMX, `bcrypt>=4.1` (new), `starlette.middleware.sessions` (already present via Starlette)
**Storage**: PostgreSQL 16 (Docker) — new tables: `users`, `invitation_codes`, `user_source_refs`; modified: `topics` (add `user_id`), `sources` (remove `topic_id`, global unique `content_hash`). ChromaDB — collection topology changes from per-topic to per-source.
**Testing**: pytest, asyncio_mode=auto, integration tests target real Postgres (Docker), no mocks of DB or auth
**Target Platform**: Linux server (Docker), macOS dev
**Project Type**: Web service + CLI
**Performance Goals**: Login/register flow completes in < 500 ms p95; no change to existing topic/content latency
**Constraints**: No JS framework. No email infrastructure. Session middleware only. YAGNI — no re-activation, no code expiry in v1.
**Scale/Scope**: Small number of users (personal/small-team tool); no horizontal scaling concerns in v1

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Question | Status |
| --------- | ------------- | ------ |
| I. Test-First | Are tests scoped to local infra only (no live LLM/remote API calls)? | ✅ Auth + CLI tests use real Postgres; no remote calls |
| II. Strong Typing | Do all new functions have fully annotated signatures? No `Any`, no bare `dict`? | ✅ All new models use Pydantic/SQLAlchemy typed models; `hash_password`/`verify_password` are fully annotated |
| III. Simplicity | Is this the simplest implementation satisfying the spec? No unapproved scope? | ✅ Cookie sessions (no JWT), argparse CLI (no Typer), no email infra, no re-activation |
| IV. Functional Style | Is side-effectful code pushed to the edges? No inheritance for reuse? | ✅ Auth helpers are pure functions; DB writes in service layer only; no new class hierarchies |
| V. Logging | Does every exception boundary log with traceback? No silent failures? | ✅ CLI errors log to stderr; auth failures log at WARN; deactivation check logs at INFO |
| Tech Stack | Python/uv, FastAPI, HTMX, PostgreSQL+Docker, no raw JS framework? | ✅ No new JS; `bcrypt` only new dep |
| Quality Gates | ruff + mypy + pytest all pass? No `Any`, no bare `dict` signatures? | ✅ All new code must pass before tasks are marked complete |

## Project Structure

### Documentation (this feature)

```text
specs/004-multi-user-isolation/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── cli.md           ← CLI subcommand contract
│   └── web-auth.md      ← Auth endpoint contract
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (additions + modifications)

```text
packages/documentlm-core/src/documentlm_core/
├── db/
│   ├── models.py                    # ADD: User, InvitationCode, UserSourceRef models
│   │                                # MODIFY: Topic (add user_id FK), Source (remove topic_id)
│   └── migrations/versions/
│       ├── 0005_create_users_and_invitation_codes.py   # NEW
│       ├── 0006_add_user_id_and_user_source_refs.py    # NEW (nullable user_id on topics)
│       ├── 0007_backfill_seed_user.py                  # NEW (assigns existing data to seed user)
│       └── 0008_apply_constraints.py                   # NEW (NOT NULL, global content_hash unique)
├── auth.py                          # NEW: hash_password(), verify_password()
└── dependencies.py                  # NEW: get_current_user_id() FastAPI dependency

apps/api/src/api/
├── main.py                          # MODIFY: add SessionMiddleware (before log_requests)
├── cli.py                           # NEW: manage entry-point (invite, reset-password, deactivate-user)
├── routers/
│   ├── auth.py                      # NEW: GET/POST /login, /logout, /register
│   ├── topics.py                    # MODIFY: filter all queries by user_id
│   ├── sources.py                   # MODIFY: use UserSourceRef for ownership; ref-count on delete
│   ├── syllabus.py                  # MODIFY: ownership check via topic.user_id
│   ├── chapters.py                  # MODIFY: ownership check via topic.user_id
│   └── bibliography.py             # MODIFY: ownership check via topic.user_id
└── templates/
    └── auth/
        ├── login.html               # NEW
        └── register.html            # NEW

packages/documentlm-core/src/documentlm_core/services/
├── chroma.py                        # MODIFY: per-source collections (source_{id.hex})
└── source.py                        # MODIFY: dedup logic uses global content_hash; creates UserSourceRef
```

**Structure Decision**: Monorepo structure unchanged. New `auth.py` and `dependencies.py` go in `documentlm-core` so both the web app and CLI can import them without circular dependencies.

## Complexity Tracking

No constitution violations. No deviations from the standard stack.

## Phase 0: Research

**Status**: Complete. See [research.md](research.md).

Key decisions:

1. **Session auth**: Starlette `SessionMiddleware` signed cookies (user_id only) — no JWT, no DB sessions table.
2. **Password hashing**: `bcrypt>=4.1` direct (not passlib).
3. **CLI**: argparse subcommands, single `manage` entry-point in `apps/api/pyproject.toml [project.scripts]`.
4. **HTMX redirects**: `HX-Redirect` header on login/logout; `302` for non-HTMX requests.
5. **Source dedup model**: `Source` becomes global (no `topic_id`); `UserSourceRef` is the per-user-per-topic link; `content_hash` globally unique.
6. **ChromaDB topology**: per-source collections (`source_{id.hex}`) replacing per-topic collections.
7. **Migration strategy**: 4 migrations (create → nullable FK → backfill seed user → NOT NULL + restructure sources).
8. **Dependency location**: `get_current_user_id` and auth helpers in `documentlm-core/dependencies.py`.

## Phase 1: Design & Contracts

**Status**: Complete.

### Data Model

See [data-model.md](data-model.md) for full entity definitions, migration plan, and ChromaDB topology change.

### Contracts

- [contracts/cli.md](contracts/cli.md) — `manage invite`, `manage reset-password`, `manage deactivate-user`
- [contracts/web-auth.md](contracts/web-auth.md) — `GET/POST /login`, `POST /logout`, `GET/POST /register`, protected route behaviour

### Key Design Decisions

**Ownership propagation**: `user_id` is placed only on `topics`. Child entities (`syllabus_items`, `atomic_chapters`, `margin_comments`) are owned transitively via the topic FK chain and existing cascade deletes. All queries that currently do `WHERE topic_id = :id` gain an implicit ownership check because the topic itself is already filtered to `WHERE user_id = :current_user_id`. No `user_id` column on child tables — YAGNI.

**Source deduplication invariant**: The application layer (service function, not raw router) is responsible for:

1. Computing `content_hash = sha256(file_bytes).hexdigest()` before inserting.
2. `SELECT source WHERE content_hash = ?` — if found, skip file storage and ChromaDB indexing.
3. `INSERT INTO user_source_refs (user_id, source_id, topic_id)` — always, whether deduped or new.
4. On user delete-source: `DELETE FROM user_source_refs WHERE user_id=? AND source_id=? AND topic_id=?`; then `SELECT COUNT(*) FROM user_source_refs WHERE source_id=?`; if 0, delete Source row and drop ChromaDB collection.

**Registration atomicity**: The `POST /register` handler runs inside a single DB transaction: (1) validate invite code `is_used=false`, (2) lock the row, (3) create user, (4) set `is_used=true`, (5) commit. Concurrent redemption of the same code is prevented by the row lock + unique constraint on `invitation_codes.code`.

**Session middleware placement**: `SessionMiddleware` must be added to `main.py` *before* the `log_requests` middleware. The `SECRET_KEY` is read from `settings.session_secret_key` (new field in `documentlm_core/config.py`).

**Protected route guard**: A FastAPI dependency `require_active_user(user_id: UUID = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> User` fetches the full `User` row and raises `401` if no session, `403` if `is_active=false`. Routers that need only the `user_id` (most of them) use the lighter `get_current_user_id` dependency.

### Agent Context Update

Run after confirming the above:

```bash
.specify/scripts/bash/update-agent-context.sh claude
```
