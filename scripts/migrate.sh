#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${DISCOVERY_COMPOSE_FILE:-${ROOT_DIR}/docker-compose.yml}"
ENV_FILE="${DISCOVERY_ENV_FILE:-${ROOT_DIR}/.env}"

if [ ! -f "${COMPOSE_FILE}" ]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "Environment file not found: ${ENV_FILE}" >&2
  exit 1
fi

read_env_value() {
  local key="$1"
  awk -F= -v key="${key}" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "${ENV_FILE}"
}

wait_for_db() {
  local db_name="${DISCOVERY_POSTGRES_DB:-$(read_env_value DISCOVERY_POSTGRES_DB)}"
  local db_user="${DISCOVERY_POSTGRES_USER:-$(read_env_value DISCOVERY_POSTGRES_USER)}"

  db_name="${db_name:-discovery}"
  db_user="${db_user:-discovery}"

  for _ in $(seq 1 30); do
    if docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T db pg_isready -U "${db_user}" -d "${db_name}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Database did not become ready in time." >&2
  return 1
}

POSTGRES_DATA_DIR="$(read_env_value DISCOVERY_POSTGRES_DATA_DIR)"
if [ -n "${POSTGRES_DATA_DIR}" ]; then
  mkdir -p "${POSTGRES_DATA_DIR}"
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d db
wait_for_db
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm --no-deps app alembic upgrade head
