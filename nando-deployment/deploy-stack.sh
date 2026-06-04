#!/usr/bin/env bash
# Build image (if needed), redeploy stack, migrate, clear-cache.
# Assets: compiled in docker build (BUILD_ASSETS_IN_IMAGE) and materialized on up by configurator.
#
# Usage:
#   ./deploy-stack.sh nando-deployment/erpnext-dev.env
#   ./deploy-stack.sh nando-deployment/erpnext-main.env --skip-build
#   ./deploy-stack.sh nando-deployment/erpnext-dev.env --skip-migrate
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
shift || true

SKIP_BUILD=0
SKIP_MIGRATE=0
for arg in "$@"; do
  case "${arg}" in
    --skip-build) SKIP_BUILD=1 ;;
    --skip-migrate) SKIP_MIGRATE=1 ;;
    *)
      echo "Unknown option: ${arg}" >&2
      echo "Usage: $0 [env-file] [--skip-build] [--skip-migrate]" >&2
      exit 1
      ;;
  esac
done

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

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
  if include_custom_app_enabled "${INCLUDE_CUSTOM_APP:-yes}" || include_hrms_enabled "${INCLUDE_HRMS:-no}"; then
    "${SCRIPT_DIR}/build-custom-image.sh" "${ENV_FILE}"
  else
    "${SCRIPT_DIR}/render-compose.sh" "${ENV_FILE}"
  fi
else
  echo "Skipping image build (--skip-build)."
fi

echo "Deploying stack (project ${COMPOSE_PROJECT_NAME})..."
compose up -d

echo "Waiting for configurator..."
configurator_id="$(compose ps -aq configurator 2>/dev/null | head -1 || true)"
if [[ -n "${configurator_id}" ]]; then
  echo "Configurator container: ${configurator_id}"
  docker wait "${configurator_id}" >/dev/null 2>&1 || true
else
  echo "Note: no configurator container id (continuing with explicit materialize)."
fi

echo "Materializing assets onto sites volume (force sync from image)..."
compose exec backend bash -c '
  set -euo pipefail
  cd /home/frappe/frappe-bench
  for app_path in apps/*; do
    [[ -d "${app_path}" ]] || continue
    app=$(basename "${app_path}")
    rm -rf "sites/assets/${app}"
  done
  FORCE_MATERIALIZE=1 bash /home/frappe/frappe-bench/materialize-assets.sh 2>/dev/null \
    || bash /home/frappe/frappe-bench/materialize-assets.sh
  if [[ ! -f sites/assets/assets.json ]]; then
    echo "No assets.json after materialize; rebuilding manifest from cached dist..."
    bench build --production --using-cached
    bash /home/frappe/frappe-bench/materialize-assets.sh
  fi
'

if [[ "${SKIP_MIGRATE}" -eq 0 ]]; then
  echo "Running migrate on ${SITE}..."
  compose exec backend bench --site "${SITE}" migrate
else
  echo "Skipping migrate (--skip-migrate)."
fi

echo "Clearing cache..."
compose exec backend bench --site "${SITE}" clear-cache
compose exec backend bench --site "${SITE}" clear-website-cache

echo "Restarting frontend..."
compose restart frontend

echo ""
echo "Asset check (frontend volume — desk + login/website bundles):"
for pattern in \
  'sites/assets/frappe/dist/css/desk.bundle.*.css' \
  'sites/assets/frappe/dist/css/website.bundle.*.css' \
  'sites/assets/frappe/dist/css/login.bundle.*.css'; do
  if ! compose exec frontend bash -c "ls ${pattern} 2>/dev/null | head -1"; then
    echo "WARNING: missing ${pattern} on frontend volume. Run:" >&2
    echo "  ./nando-deployment/setup-assets.sh ${ENV_FILE}" >&2
  fi
done
if ! compose exec backend test -f sites/assets/assets.json; then
  echo "WARNING: sites/assets/assets.json missing. Run setup-assets.sh or bench build --using-cached." >&2
fi

echo ""
echo "Deploy complete."
echo "  Site: ${SITE}"
echo "  Compose: ${COMPOSE_FILE_OUTPUT}"
echo ""
compose ps
