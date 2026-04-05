#!/bin/bash
set -e

# Start postgres in Docker
docker compose -f docker-compose.dev.yml up -d

# Wait for postgres to be ready
echo "Waiting for postgres..."
until docker compose -f docker-compose.dev.yml exec -T postgres pg_isready -q; do
  sleep 1
done

# Load .env
set -a
source .env
set +a

export DEV_PASSWORD=devPassword1234
# Override DB host for local dev — .env uses 'db' (Docker service name) for prod
export DATABASE_URL=postgresql+asyncpg://tracker:tracker@localhost:5432/tracker

# Run migrations then start the app
uv run alembic upgrade head
DEBUG=true LOG_LEVEL=INFO uv run --project apps/api uvicorn api.main:create_app --factory --reload --app-dir apps/api/src
