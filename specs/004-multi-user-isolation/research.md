# Research: Multi-User Isolation (004)

## Decision 1 — Session Authentication Strategy

**Decision**: Starlette `SessionMiddleware` with signed cookies; store only `user_id` (UUID) in the session.

**Rationale**: The app is server-rendered HTMX, not a SPA. Cookie sessions require no extra table, no token refresh logic, and integrate directly with FastAPI's `request.session` dict. The cookie is signed with a server secret (HMAC-SHA256 via `itsdangerous`), which ships with Starlette. JWT would require either a blocklist table (for revocation) or no revocation—an unnecessary tradeoff for a small app.

**Alternatives considered**:
- JWT (Bearer): rejected — requires either a blocklist table or accepting unrevocable tokens; overhead not justified for a server-rendered app.
- Database sessions: rejected — adds a `sessions` table and a DB lookup per request; unnecessary complexity (YAGNI).

**Key configuration**:
```
max_age = 604800  # 7 days
https_only = True in production (False when DEBUG=true)
samesite = "lax"   # CSRF-safe for form submissions and HTMX XHR
```

**Middleware ordering**: `SessionMiddleware` must be added to the app *before* the existing `log_requests` middleware so that `request.session` is populated when the logging middleware runs.

---

## Decision 2 — Password Hashing Library

**Decision**: `bcrypt>=4.1` (direct, not via `passlib`).

**Rationale**: `passlib` is in low-maintenance mode; `bcrypt` is actively maintained and purpose-built for password hashing. It handles salt generation internally. Cost factor 12 yields ~100 ms per hash, which is the accepted security/UX balance for login.

**Alternatives considered**:
- `passlib[bcrypt]`: rejected — adds a transitive dependency with no benefit here.
- `hashlib.scrypt`: rejected — requires manual salt management; a general KDF, not password-specific; less community guidance on correct parameterisation.

**Where to add**: `apps/api/pyproject.toml` dependencies. Helper functions (`hash_password`, `verify_password`) live in `packages/documentlm-core/src/documentlm_core/auth.py` so both web app and CLI can import them.

---

## Decision 3 — CLI Structure

**Decision**: Single `manage` entry-point with argparse subcommands; registered in `apps/api/pyproject.toml` `[project.scripts]`.

**Rationale**: Multiple standalone scripts scatter tooling; a single entry-point (`manage invite`, `manage reset-password`, `manage deactivate-user`) is self-documenting via `manage --help`. argparse is stdlib—no extra dependency. The entry-point runs `asyncio.run(...)` to reuse the existing async DB session factory.

**Alternatives considered**:
- Typer/Click: rejected — adds a dependency for functionality stdlib covers; spec says simplest approach.
- Separate scripts per operation: rejected — harder to discover and document.

**Invocation**:
```
uv run manage invite
uv run manage reset-password user@example.com
uv run manage deactivate-user user@example.com
```

---

## Decision 4 — HTMX Auth Redirects

**Decision**: Return `200 OK` with `HX-Redirect` response header for HTMX-triggered login/logout; return `302` for non-HTMX full-page requests.

**Rationale**: HTMX sends XHR requests; a `302` inside XHR does not trigger browser navigation—the browser follows the redirect silently and HTMX replaces the target element with the login page HTML, breaking the UI. `HX-Redirect` instructs HTMX to perform a full browser navigation to the given URL.

**Detection**: Check `request.headers.get("HX-Request") == "true"` to distinguish HTMX from regular requests. Unauthenticated access to a protected page that is loaded directly (non-HTMX) should return a `302` to `/login`.

**Alternatives considered**:
- Always return 302: rejected — breaks HTMX partial requests.
- Return 401 JSON: rejected — app is HTML-first; JSON error responses don't render in templates.

---

## Decision 5 — Source Deduplication Model

**Decision**: Promote `Source` to a globally-scoped record (no `topic_id`); introduce `UserSourceRef` join table as the per-user, per-topic link. `content_hash` becomes a global unique constraint.

**Rationale**: The current model has `Source.topic_id` and a unique constraint on `(topic_id, content_hash)`. This allows the same file to be stored twice under two different topics — even for the same user. For cross-user deduplication we need global uniqueness. Removing `topic_id` from `Source` and putting it in `UserSourceRef` achieves deduplication cleanly: two users adding the same file find the same `Source` row; each gets their own `UserSourceRef` pointing to it.

**Alternatives considered**:
- Keep `topic_id` on `Source`, add a separate global dedup table: rejected — two sources of truth for the same physical file.
- Deduplicate only at file storage (filesystem) but not in DB: rejected — ref counting requires a single DB record to decrement.

---

## Decision 6 — ChromaDB Collection Topology

**Decision**: Change from per-topic collections (`topic_{topic_id.hex}`) to per-source collections (`source_{source_id.hex}`).

**Rationale**: Currently chunks are stored in a collection named after the topic. If two users add the same source, the same chunks would need to be in both users' topic collections—defeating deduplication. Per-source collections mean embeddings are computed once; queries filter by `source_id` set derived from the user's `UserSourceRef` rows.

**Alternatives considered**:
- Single global collection with metadata filtering: viable, but makes collection deletion (on ref-count zero) less clean than dropping a dedicated collection.
- Keep per-topic, duplicate embeddings: rejected — violates the spec requirement.

---

## Decision 7 — Migration Strategy for Existing Data

**Decision**: 3-step migration: (1) create new tables + add nullable `user_id` FK to `topics`; (2) backfill—assign all existing topics to a system/seed user created in the migration; (3) apply `NOT NULL` constraint.

**Rationale**: Avoids locking issues on `ALTER COLUMN`. The spec assumption states existing data will be migrated to a default seed user; a deterministic seed UUID (hardcoded in the migration) makes this reproducible.

**Source restructuring migration**: Add a separate migration that (1) creates `user_source_refs`, (2) backfills one `UserSourceRef` per existing `Source` (assigned to the seed user, using existing `topic_id`), (3) drops `topic_id` from `Source`, (4) adds global unique constraint on `content_hash`.

---

## Decision 8 — `get_current_user` FastAPI Dependency Location

**Decision**: Define `get_current_user_id` in `packages/documentlm-core/src/documentlm_core/dependencies.py`.

**Rationale**: The CLI and any future package also need auth helpers; keeping them in `documentlm-core` avoids importing from `apps/api` (which would create a circular dependency). All existing routers already import from `documentlm_core`; the pattern is consistent.
