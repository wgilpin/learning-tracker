# Quickstart: Multi-User Isolation (004)

## Prerequisites

- Docker + Docker Compose
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- A `.env` file (copy from `.env.example`, add `SESSION_SECRET_KEY`)

## Environment Variables (additions for this feature)

Add to `.env`:

```
SESSION_SECRET_KEY=<random-64-char-hex>   # Required — signs session cookies
```

Generate a value:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## First-time Setup

```bash
# 1. Start Postgres
docker compose -f docker-compose.dev.yml up -d

# 2. Run all migrations (includes new users, invitation_codes, user_source_refs tables)
uv run alembic upgrade head

# 3. Generate your first invitation code
uv run manage invite
# Prints: INV-<32-char-hex>

# 4. Start the app
bash dev.sh
```

Open `http://localhost:8000/register`, paste the invitation code, and create your account.

## Adding More Users

Each new user needs their own invitation code:

```bash
uv run manage invite
# Share the printed code with the new user out-of-band
```

## Operator Commands

```bash
# Generate invitation code
uv run manage invite

# Reset a user's password
uv run manage reset-password user@example.com newpassword123

# Deactivate a user (blocks login, keeps all data)
uv run manage deactivate-user user@example.com
```

## Running Tests

```bash
# Unit tests only (no Docker needed)
uv run pytest -m unit

# Integration tests (requires Postgres running)
docker compose -f docker-compose.dev.yml up -d
uv run pytest -m integration
```

## Migration Notes (upgrading from single-user)

Migrations 0005–0008 run automatically with `alembic upgrade head`. They:

1. Create `users`, `invitation_codes`, `user_source_refs` tables.
2. Add `user_id` (nullable) to `topics`.
3. Assign all existing topics + sources to seed user `00000000-0000-0000-0000-000000000001`.
4. Apply NOT NULL constraint; restructure `sources` (remove `topic_id`, make `content_hash` globally unique).

After migrating, reset the seed user's password to take ownership of existing data:

```bash
uv run manage reset-password seed@localhost <your-password>
```

(The seed user's email is `seed@localhost` — set in migration 0007.)
