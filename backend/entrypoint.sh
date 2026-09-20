#!/bin/sh
# EPIC — Backend Container Entrypoint
# Applies Alembic migrations before the app starts, so the schema in every
# environment (dev, staging, prod) comes from tracked revisions rather than
# an ad-hoc create_all() at import time. See backend/alembic/versions/.
set -e

echo "[entrypoint] Running database migrations (alembic upgrade head)..."
alembic upgrade head
echo "[entrypoint] Migrations applied."

echo "[entrypoint] Starting: $*"
exec "$@"
