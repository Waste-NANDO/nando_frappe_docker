#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-erpnext}"
COMPOSE_FILE_OUTPUT="${COMPOSE_FILE_OUTPUT:-${SCRIPT_DIR}/erpnext.yaml}"
if [[ "${COMPOSE_FILE_OUTPUT}" != /* ]]; then
  COMPOSE_FILE_OUTPUT="${REPO_ROOT}/${COMPOSE_FILE_OUTPUT}"
fi

docker compose --project-name "${COMPOSE_PROJECT_NAME}" \
  --env-file "${ENV_FILE}" \
  -f "${REPO_ROOT}/compose.yaml" \
  -f "${REPO_ROOT}/overrides/compose.redis.yaml" \
  -f "${REPO_ROOT}/overrides/compose.mariadb.yaml" \
  -f "${SCRIPT_DIR}/compose.custom-tls.yaml" \
  -f "${SCRIPT_DIR}/compose.backup.yaml" \
  config > "${COMPOSE_FILE_OUTPUT}"

echo "Rendered compose file: ${COMPOSE_FILE_OUTPUT}"
echo "Compose project: ${COMPOSE_PROJECT_NAME}"
echo "Env file: ${ENV_FILE}"
