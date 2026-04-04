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

# Run migrations then start the app
uv run alembic upgrade head
DEBUG=true uv run --project apps/api uvicorn api.main:create_app --factory --reload --app-dir apps/api/src
