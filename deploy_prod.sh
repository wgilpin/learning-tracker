#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker/compose.prod.yml"

# Build context must be ~/projects/ (two levels up — Dockerfile copies nlp_utils from there)
BUILD_CONTEXT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$SCRIPT_DIR"


echo "==> Building and restarting services"
docker compose -f "$COMPOSE_FILE" build --build-arg BUILDKIT_INLINE_CACHE=1
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

echo "==> Waiting for api to be healthy"
for i in $(seq 1 30); do
  STATUS=$(docker compose -f "$COMPOSE_FILE" ps --format json api 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Health',''))" 2>/dev/null || echo "")
  if [ "$STATUS" = "healthy" ]; then
    break
  fi
  sleep 2
done

echo "==> Deploy complete"
docker compose -f "$COMPOSE_FILE" ps
