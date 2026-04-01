# Tasks: Multi-User Isolation

**Input**: Design documents from `/specs/004-multi-user-isolation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, contracts/web-auth.md

**Tests**: Included per constitution (TDD is mandatory — tests MUST be written first and MUST fail before implementation begins).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are included in all descriptions

## Path Conventions

This is a uv-workspace monorepo. Key roots:
- `packages/documentlm-core/src/documentlm_core/` — shared engine (models, services, auth, migrations)
- `apps/api/src/api/` — FastAPI web app (routers, templates, cli, main)
- `apps/api/tests/` — all tests (unit/, integration/)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency and configuration changes that all later phases depend on. No logic yet.

- [X] T001 Add `bcrypt>=4.1` to `apps/api/pyproject.toml` dependencies and run `uv lock` to update the lockfile
- [X] T002 [P] Add `session_secret_key: str` field to `packages/documentlm-core/src/documentlm_core/config.py` Settings model (reads from env var `SESSION_SECRET_KEY`; provide a non-empty default only for tests)
- [X] T003 [P] Add `[project.scripts]` entry `manage = "api.cli:main"` to `apps/api/pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB schema and auth helpers that MUST exist before any user story implementation begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Add `User` and `InvitationCode` SQLAlchemy models to `packages/documentlm-core/src/documentlm_core/db/models.py` — `User` (id UUID PK, email VARCHAR(320) unique, password_hash VARCHAR(60), is_active bool default true, created_at, deactivated_at nullable); `InvitationCode` (code VARCHAR(64) PK, is_used bool default false, created_at, used_at nullable, used_by_user_id UUID FK→users nullable)
- [X] T005 Write Alembic migration `0005_create_users_and_invitation_codes.py` in `packages/documentlm-core/src/documentlm_core/db/migrations/versions/` — creates `users` table with unique index on `email`; creates `invitation_codes` table; verify `uv run alembic upgrade head` applies cleanly and `downgrade` reverses it
- [X] T006 [P] Create `packages/documentlm-core/src/documentlm_core/auth.py` with two fully-typed pure functions: `hash_password(password: str) -> str` (bcrypt rounds=12) and `verify_password(password: str, hashed: str) -> bool`

**Checkpoint**: Foundation ready — user story phases can now begin.

---

## Phase 3: User Story 1 — Invitation Code Generation (Priority: P1) 🎯 MVP

**Goal**: Operator can run `manage invite` to generate a unique single-use code, printed to stdout and persisted in the DB.

**Independent Test**: Run `uv run manage invite`, confirm one line printed to stdout matching `INV-<hex>`, then query DB and confirm a matching `invitation_codes` row with `is_used=false`.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before T009

- [X] T007 [P] [US1] Write integration test `test_cli_invite_generates_code` in `apps/api/tests/integration/test_cli_invite.py` — calls `manage invite` via `subprocess.run`, asserts exit code 0, asserts stdout matches `INV-[0-9a-f]{32}`, asserts exactly one `invitation_codes` row exists in the test DB with `is_used=false`
- [X] T008 [P] [US1] Write integration test `test_cli_invite_each_call_unique` in `apps/api/tests/integration/test_cli_invite.py` — calls `manage invite` twice, asserts two distinct codes exist in DB
- [X] T009 [P] [US1] Write integration test `test_cli_invite_db_error` in `apps/api/tests/integration/test_cli_invite.py` — runs CLI with invalid DATABASE_URL, asserts exit code 1 and stderr contains "Error:"

### Implementation for User Story 1

- [X] T010 [US1] Create `packages/documentlm-core/src/documentlm_core/services/invitation.py` — single async function `create_invitation_code(session: AsyncSession) -> str` that generates a 32-byte hex token prefixed `INV-`, inserts an `InvitationCode` row, commits, and returns the code string
- [X] T011 [US1] Create `apps/api/src/api/cli.py` with argparse `main()` entry-point and `invite` subcommand — calls `asyncio.run(create_invitation_code(...))` using `AsyncSessionFactory`, prints code to stdout, exits 0; on any exception logs to stderr and exits 1; all functions fully typed

**Checkpoint**: `uv run manage invite` works end-to-end. US1 tests pass.

---

## Phase 4: User Story 2 — Join by Invitation Code and Login (Priority: P2)

**Goal**: New users register using a valid single-use invite code; existing users log in with email + password; operator can reset passwords and deactivate accounts via CLI.

**Independent Test**: Generate a code via CLI; visit `/register`, submit the code + credentials; confirm redirect to `/`; log out; log back in; confirm dashboard shows only that user's data. Attempt to reuse the code — confirm rejection.

### Tests for User Story 2 ⚠️ Write FIRST — must FAIL before T018

- [X] T012 [P] [US2] Write integration tests `test_register_*` in `apps/api/tests/integration/test_auth.py` — covers: valid invite code creates user + sets session + redirects (HX-Redirect or 302); used code is rejected (400); invalid code is rejected (400); duplicate email is rejected (409); password mismatch is rejected (422)
- [X] T013 [P] [US2] Write integration tests `test_login_*` in `apps/api/tests/integration/test_auth.py` — covers: correct credentials set session + redirect; wrong password returns 401 with form re-render; deactivated user returns 403; unauthenticated access to `/` redirects to `/login`
- [X] T014 [P] [US2] Write integration tests `test_cli_reset_password` and `test_cli_deactivate_user` in `apps/api/tests/integration/test_cli_invite.py` — reset-password: correct user gets updated hash, wrong email exits 1; deactivate-user: sets is_active=false + deactivated_at, already-deactivated user exits 1

### Implementation for User Story 2

- [X] T015 [US2] Add `SessionMiddleware` to `apps/api/src/api/main.py` — import from `starlette.middleware.sessions`, add before the existing `log_requests` middleware, pass `secret_key=settings.session_secret_key`, `max_age=604800`, `https_only=not settings.debug`, `samesite="lax"`
- [X] T016 [US2] Create `packages/documentlm-core/src/documentlm_core/dependencies.py` with two FastAPI dependencies: `get_current_user_id(request: Request) -> uuid.UUID` (reads `request.session["user_id"]`, raises 401 if absent); `require_active_user(user_id: UUID = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> User` (fetches User row, raises 403 if `is_active=false`)
- [X] T017 [US2] Create `packages/documentlm-core/src/documentlm_core/services/user.py` with fully-typed async functions: `create_user_from_invite(session, code, email, password) -> User` (transactionally validates + consumes invite code, creates User row); `authenticate_user(session, email, password) -> User | None`; `get_user_by_email(session, email) -> User | None`
- [X] T018 [US2] Create `apps/api/src/api/routers/auth.py` — `GET /login` (render login.html, redirect to `/` if already authenticated); `POST /login` (authenticate, set session, HX-Redirect or 302); `POST /logout` (clear session, HX-Redirect or 302 to /login); `GET /register` (render register.html); `POST /register` (call create_user_from_invite, set session, HX-Redirect or 302); all error cases re-render form with message
- [X] T019 [P] [US2] Create `apps/api/src/api/templates/auth/login.html` — extends base layout; form with email + password fields; HTMX `hx-post="/login"`; displays error message if present
- [X] T020 [P] [US2] Create `apps/api/src/api/templates/auth/register.html` — extends base layout; form with invite_code, email, password, password_confirm fields; HTMX `hx-post="/register"`; displays error message if present
- [X] T021 [US2] Register auth router in `apps/api/src/api/main.py` and add global unauthenticated-redirect guard: middleware or dependency that intercepts requests to all routes except `/login`, `/register`, `/static/*` and redirects (302 or HX-Redirect) unauthenticated users to `/login`
- [X] T022 [US2] Add `reset-password <email> <new-password>` subcommand to `apps/api/src/api/cli.py` — validates user exists, hashes new password via `hash_password`, updates `users.password_hash`, prints confirmation; exits 1 with error on stderr if user not found
- [X] T023 [US2] Add `deactivate-user <email>` subcommand to `apps/api/src/api/cli.py` — sets `is_active=false` and `deactivated_at=now()`, prints confirmation; exits 1 if user not found or already deactivated

**Checkpoint**: Full auth lifecycle works. US2 tests pass. All three CLI subcommands functional.

---

## Phase 5: User Story 3 — Per-User Course and Content Ownership (Priority: P3)

**Goal**: All topics, syllabus items, chapters, and progress are scoped to the authenticated user. No user can see or modify another user's data via any route.

**Independent Test**: Create topics as user A and user B. Log in as each — confirm each sees only their own topics. Attempt to fetch user B's topic ID as user A (direct URL) — confirm 404 (not 403, to avoid revealing existence).

### Tests for User Story 3 ⚠️ Write FIRST — must FAIL before T028

- [X] T024 [P] [US3] Write integration tests `test_topic_isolation_*` in `apps/api/tests/integration/test_access_control.py` — user A creates topic; user B lists topics (empty); user B GETs user A's topic ID (404); user B attempts to DELETE user A's topic (404)
- [X] T025 [P] [US3] Write integration tests `test_child_isolation_*` in `apps/api/tests/integration/test_access_control.py` — user A creates topic with syllabus item; user B cannot access that syllabus item; user A marks progress; user B has no progress record

### Implementation for User Story 3

- [X] T026 [US3] Write Alembic migration `0006_add_user_id_nullable_to_topics.py` in `packages/documentlm-core/src/documentlm_core/db/migrations/versions/` — adds nullable `user_id` UUID FK column to `topics` referencing `users.id ON DELETE CASCADE`; adds index `topics_user_id_idx`; verify upgrade + downgrade
- [X] T027 [US3] Write Alembic migration `0007_backfill_seed_user.py` — creates seed user row with id `00000000-0000-0000-0000-000000000001`, email `seed@localhost`, and a bcrypt hash of a placeholder password; `UPDATE topics SET user_id = '00000000-...' WHERE user_id IS NULL`; verify upgrade only (downgrade is no-op)
- [X] T028 [US3] Write Alembic migration `0008_topics_user_id_not_null.py` — applies `NOT NULL` constraint to `topics.user_id`; verify upgrade + downgrade
- [X] T029 [US3] Update `Topic` SQLAlchemy model in `packages/documentlm-core/src/documentlm_core/db/models.py` — add `user_id: Mapped[uuid.UUID]` column with `ForeignKey("users.id", ondelete="CASCADE")`; add `user: Mapped[User]` relationship
- [X] T030 [US3] Update `apps/api/src/api/routers/topics.py` — add `user_id: uuid.UUID = Depends(get_current_user_id)` to all handlers; filter all `SELECT` queries with `WHERE topics.user_id = :user_id`; `GET /topics/{id}` returns 404 (not 403) if topic not found for that user; `POST /topics` sets `topic.user_id = user_id`
- [X] T031 [P] [US3] Update `apps/api/src/api/routers/syllabus.py` — add `get_current_user_id` dependency; all handlers resolve topic first with `user_id` filter; return 404 if topic not owned by current user
- [X] T032 [P] [US3] Update `apps/api/src/api/routers/chapters.py` — same ownership pattern as T031
- [X] T033 [P] [US3] Update `apps/api/src/api/routers/bibliography.py` — same ownership pattern as T031

**Checkpoint**: All topic/content routes enforce user isolation. US3 tests pass.

---

## Phase 6: User Story 4 — Source Document Deduplication with Reference Counting (Priority: P4)

**Goal**: Identical documents (by SHA-256 content hash) are stored once; each user has their own reference. Deleting a source decrements the ref count; the physical file and ChromaDB collection are removed only when the count reaches zero.

**Independent Test**: Upload the same PDF as user A and user B — confirm one `sources` row and one ChromaDB `source_*` collection exist. Delete as user A — user B's source still returns results. Delete as user B — `sources` row and ChromaDB collection are gone.

### Tests for User Story 4 ⚠️ Write FIRST — must FAIL before T038

- [ ] T034 [P] [US4] Write integration test `test_source_dedup_shared_storage` in `apps/api/tests/integration/test_source_dedup.py` — user A and user B upload the same PDF bytes; assert exactly one `sources` row and two `user_source_refs` rows exist
- [ ] T035 [P] [US4] Write integration test `test_source_ref_count_delete` in `apps/api/tests/integration/test_source_dedup.py` — both users have the source; user A deletes it; assert `sources` row still exists, one `user_source_refs` row remains; user B deletes it; assert `sources` row is gone and ChromaDB collection `source_{id.hex}` no longer exists
- [ ] T036 [P] [US4] Write integration test `test_source_query_after_partial_delete` in `apps/api/tests/integration/test_source_dedup.py` — user A deletes shared source; user B queries topic; source chunks still returned correctly

### Implementation for User Story 4

- [ ] T037 [US4] Write Alembic migration `0009_user_source_refs_and_source_restructure.py` in `packages/documentlm-core/src/documentlm_core/db/migrations/versions/` — (1) creates `user_source_refs` table (id UUID PK, user_id FK, source_id FK, topic_id FK, created_at, UNIQUE on (user_id, source_id, topic_id)); (2) backfills one `user_source_refs` row per existing `sources` row using the seed user and existing `sources.topic_id`; (3) drops `topic_id` column from `sources`; (4) drops old unique constraint `(topic_id, content_hash)` and adds global UNIQUE constraint on `content_hash` alone; verify upgrade + downgrade
- [ ] T038 [US4] Add `UserSourceRef` SQLAlchemy model to `packages/documentlm-core/src/documentlm_core/db/models.py`; remove `topic_id` FK from `Source` model; update `Source` unique constraint to `UniqueConstraint("content_hash")`; add `user_source_refs` relationship to `Source`
- [ ] T039 [US4] Update `packages/documentlm-core/src/documentlm_core/services/chroma.py` — rename collections from `topic_{topic_id.hex}` to `source_{source_id.hex}`; update `upsert_source_chunks` to use `source_id` as collection name; update `query_topic_chunks_with_sources` to accept a list of `source_id`s (from `UserSourceRef`) and query each per-source collection; add `delete_source_collection(source_id: UUID)` function
- [ ] T040 [US4] Update `packages/documentlm-core/src/documentlm_core/services/source.py` — rewrite `add_source_for_user(session, user_id, topic_id, ...) -> Source` to: compute SHA-256 of content; `SELECT sources WHERE content_hash = ?`; if found, skip file storage + ChromaDB indexing; always create `UserSourceRef`; rewrite `delete_source_for_user(session, user_id, source_id, topic_id)` to: delete `UserSourceRef`; count remaining refs; if 0, delete `Source` row and call `delete_source_collection`
- [ ] T041 [US4] Update `apps/api/src/api/routers/sources.py` — replace direct `Source` ownership queries with `UserSourceRef`-based queries filtered by `(user_id, topic_id)`; wire source addition to `add_source_for_user`; wire deletion to `delete_source_for_user`; add `get_current_user_id` dependency to all handlers

**Checkpoint**: Source deduplication and ref-count deletion work end-to-end. US4 tests pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, cleanup, and final validation across all stories.

- [ ] T042 [P] Run `uv run ruff check .` and `uv run ruff format .` across the entire workspace — fix all lint errors in new and modified files
- [ ] T043 [P] Run `uv run mypy` in strict mode on `packages/documentlm-core` and `apps/api` — fix all type errors; confirm zero `Any` and zero unparameterised `dict` in new code
- [ ] T044 Drop orphaned ChromaDB `topic_*` collections: add a one-time CLI helper or migration note in `quickstart.md` instructing operators to run `uv run manage cleanup-chroma` (or equivalent) after upgrading — document in `specs/004-multi-user-isolation/quickstart.md`
- [ ] T045 Validate full quickstart flow against `specs/004-multi-user-isolation/quickstart.md` — fresh DB, `alembic upgrade head`, `manage invite`, register, create topic, add source, verify isolation with a second user

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T002 and T003 are parallel
- **Phase 2 (Foundation)**: Depends on Phase 1; T006 is parallel with T004/T005
- **Phase 3 (US1)**: Depends on Phase 2 — T007/T008/T009 tests parallel; T010/T011 implement sequentially after tests fail
- **Phase 4 (US2)**: Depends on Phase 2 — tests T012/T013/T014 parallel; implementation sequential within phase
- **Phase 5 (US3)**: Depends on Phase 4 (auth must exist to test isolation) — tests T024/T025 parallel; migrations T026→T027→T028 sequential; router updates T031/T032/T033 parallel after T030
- **Phase 6 (US4)**: Depends on Phase 5 (topic ownership must be in place) — tests T034/T035/T036 parallel; T037→T038→T039→T040→T041 sequential
- **Phase 7 (Polish)**: Depends on Phase 6

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundation (Phase 2) — no dependency on other stories
- **US2 (P2)**: Depends only on Foundation (Phase 2) — independently testable
- **US3 (P3)**: Depends on US2 (auth system must exist to authenticate test users)
- **US4 (P4)**: Depends on US3 (topic ownership pattern must be in place for user_source_refs)

### Within Each User Story

1. Write all tests for the story — confirm they **FAIL** (Red)
2. Implement models/services
3. Implement endpoints/CLI
4. Confirm tests pass (Green)
5. Refactor if needed, re-run quality gates

### Parallel Opportunities

- T002, T003 (Phase 1): parallel — different files
- T006 (Phase 2): parallel with T004/T005 — different file
- T007, T008, T009 (US1 tests): parallel — same test file but independent test functions; write sequentially, run in parallel
- T012, T013, T014 (US2 tests): parallel — independent test functions
- T019, T020 (US2 templates): parallel — different files
- T024, T025 (US3 tests): parallel — independent test functions
- T031, T032, T033 (US3 router updates): parallel — different files, same ownership pattern
- T034, T035, T036 (US4 tests): parallel — independent test functions
- T042, T043 (Polish): parallel — different tools

---

## Parallel Example: User Story 3

```
# Write tests in parallel (same file, independent functions):
Task T024: test_topic_isolation_* in test_access_control.py
Task T025: test_child_isolation_* in test_access_control.py

# After T030 (topics router updated), update other routers in parallel:
Task T031: syllabus.py ownership check
Task T032: chapters.py ownership check
Task T033: bibliography.py ownership check
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (manage invite CLI)
4. **STOP and VALIDATE**: `uv run manage invite` works; test suite passes
5. Proceed to US2 only when MVP is validated

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) → CLI invite works → validate
3. Phase 4 (US2) → Auth + register/login works → validate
4. Phase 5 (US3) → Full data isolation → validate
5. Phase 6 (US4) → Source deduplication → validate
6. Phase 7 → Quality gates + cleanup

---

## Notes

- **[P]** tasks operate on different files with no unresolved upstream dependencies
- **[Story]** label maps each task to its user story for traceability
- Constitution mandates TDD: every test task must be completed and confirmed **failing** before the implementation task it covers
- Return 404 (not 403) when a user requests another user's resource — avoids leaking existence
- Seed user UUID `00000000-0000-0000-0000-000000000001` is set in migration 0007; reset its password after deploying: `uv run manage reset-password seed@localhost <password>`
- ChromaDB collection rename (`topic_*` → `source_*`) is a breaking change; existing embeddings must be re-indexed after migration 0009
