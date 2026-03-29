#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/data

if [ "${WEB_CONCURRENCY:-1}" != "1" ]; then
  echo "WARNING: WEB_CONCURRENCY is greater than 1 while analysis jobs still run in-process." >&2
fi

exec gunicorn \
  app:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_CONCURRENCY:-1}" \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout "${DISCOVERY_GUNICORN_TIMEOUT:-180}" \
  --graceful-timeout "${DISCOVERY_GUNICORN_GRACEFUL_TIMEOUT:-30}" \
  --access-logfile - \
  --error-logfile -
