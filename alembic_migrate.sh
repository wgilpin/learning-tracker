#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker/compose.prod.yml"

echo "==> Running Alembic schema migrations"
docker compose -f "$COMPOSE_FILE" exec api uv run alembic upgrade head
echo "==> Done"
