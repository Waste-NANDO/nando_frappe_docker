#!/usr/bin/env bash
# Sync Desk assets on the shared sites volume.
#
# Default (BUILD_ASSETS_IN_IMAGE=yes): materialize + clear-cache + restart frontend
#   — bundles already compiled during docker build.
#
# --full: bench build --force + materialize + clear-cache + restart frontend
#   — use when BUILD_ASSETS_IN_IMAGE=no or you changed app JS without rebuilding the image.
#
# Usage:
#   ./setup-assets.sh nando-deployment/erpnext-dev.env
#   ./setup-assets.sh nando-deployment/erpnext-dev.env --full
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
shift || true

FULL_BUILD=0
for arg in "$@"; do
  case "${arg}" in
    --full) FULL_BUILD=1 ;;
    *)
      echo "Unknown option: ${arg}" >&2
      echo "Usage: $0 [env-file] [--full]" >&2
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
BUILD_ASSETS_IN_IMAGE="${BUILD_ASSETS_IN_IMAGE:-yes}"

compose() {
  docker compose --project-name "${COMPOSE_PROJECT_NAME}" -f "${COMPOSE_FILE_OUTPUT}" "$@"
}

run_bench_build=0
if [[ "${FULL_BUILD}" -eq 1 ]]; then
  run_bench_build=1
elif ! build_assets_in_image_enabled "${BUILD_ASSETS_IN_IMAGE}"; then
  run_bench_build=1
fi

if [[ "${run_bench_build}" -eq 1 ]]; then
  echo "Building assets in backend (this may take 10–15 minutes with HRMS)..."
  compose exec backend bench build --force
else
  echo "Skipping bench build (assets baked in image; use --full to rebuild on the server)."
fi

echo "Materializing assets onto the shared sites volume..."
compose exec backend bash -c '
  set -euo pipefail
  cd /home/frappe/frappe-bench
  for app_path in apps/*; do
    [[ -d "${app_path}" ]] || continue
    app=$(basename "${app_path}")
    rm -rf "sites/assets/${app}"
  done
  FORCE_MATERIALIZE=1 bash /home/frappe/frappe-bench/materialize-assets.sh
'

echo "Verifying login/website bundles on frontend volume..."
verify_failed=0
for pattern in \
  'sites/assets/frappe/dist/css/website.bundle.*.css' \
  'sites/assets/frappe/dist/css/login.bundle.*.css' \
  'sites/assets/erpnext/dist/css/erpnext-web.bundle.*.css'; do
  if ! compose exec frontend bash -c "ls ${pattern} 2>/dev/null | head -1"; then
    echo "WARNING: missing ${pattern}" >&2
    verify_failed=1
  fi
done
if [[ "${verify_failed}" -ne 0 ]]; then
  echo "Try: $0 ${ENV_FILE} --full" >&2
fi

echo "Clearing caches for ${SITE}..."
compose exec backend bench --site "${SITE}" clear-cache
compose exec backend bench --site "${SITE}" clear-website-cache

echo "Restarting frontend..."
compose restart frontend

echo "Done. Verify:"
compose exec frontend bash -c 'ls sites/assets/frappe/dist/css/desk.bundle.*.css | head -1'
compose exec backend bash -c 'ls apps/frappe/frappe/public/dist/css/desk.bundle.*.css 2>/dev/null | head -1 || ls apps/frappe/public/dist/css/desk.bundle.*.css 2>/dev/null | head -1'
