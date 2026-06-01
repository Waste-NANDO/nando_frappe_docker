#!/usr/bin/env bash
# Build JS/CSS bundles in backend and copy them to the shared sites volume.
# Run once after deploy or when apps change (needs ~4GB+ free RAM on the host).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-erpnext}"
COMPOSE_FILE_OUTPUT="${COMPOSE_FILE_OUTPUT:-${SCRIPT_DIR}/erpnext-dev.yaml}"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ "${COMPOSE_FILE_OUTPUT}" != /* ]]; then
  COMPOSE_FILE_OUTPUT="${REPO_ROOT}/${COMPOSE_FILE_OUTPUT}"
fi

SITE="${FRAPPE_SITE_NAME_HEADER:-apps.internal.nandoai.com}"

compose() {
  docker compose --project-name "${COMPOSE_PROJECT_NAME}" -f "${COMPOSE_FILE_OUTPUT}" "$@"
}

echo "Building assets (this may take 10–15 minutes with HRMS)..."
compose exec backend bench build --force

echo "Materializing assets onto the shared sites volume..."
compose exec backend bash /home/frappe/frappe-bench/materialize-assets.sh

echo "Clearing caches for ${SITE}..."
compose exec backend bench --site "${SITE}" clear-cache
compose exec backend bench --site "${SITE}" clear-website-cache

echo "Restarting frontend..."
compose restart frontend

echo "Done. Verify:"
compose exec frontend bash -c 'ls sites/assets/frappe/dist/css/website.bundle.*.css | head -1'
