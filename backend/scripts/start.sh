#!/usr/bin/env sh
set -eu

: "${APP_HOST:=0.0.0.0}"
: "${APP_PORT:=8000}"
: "${MIGRATION_ATTEMPTS:=30}"
export APP_HOST APP_PORT

echo "[start] applying database migrations"
attempt=1
while ! alembic upgrade head; do
    if [ "$attempt" -ge "$MIGRATION_ATTEMPTS" ]; then
        echo "[start] migrations failed after $attempt attempt(s)" >&2
        exit 1
    fi
    echo "[start] database is not ready (attempt $attempt/$MIGRATION_ATTEMPTS), retrying in 2s"
    attempt=$((attempt + 1))
    sleep 2
done
echo "[start] database schema is up to date"

echo "[start] starting API on $APP_HOST:$APP_PORT"
exec uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT"
