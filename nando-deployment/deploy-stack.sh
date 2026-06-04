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

verify_assets_manifest() {
  local service="$1"

  compose exec -T "${service}" python3 - <<'PY'
from pathlib import Path
import json
import re
import sys

assets = Path("sites/assets")
manifest = assets / "assets.json"

if not manifest.is_file():
    print(f"[asset-check] missing {manifest}", file=sys.stderr)
    sys.exit(1)

try:
    data = json.loads(manifest.read_text())
except Exception as exc:
    print(f"[asset-check] invalid {manifest}: {exc}", file=sys.stderr)
    sys.exit(1)

text = json.dumps(data)
refs = sorted(set(re.findall(
    r"(?:/assets/)?([A-Za-z0-9_.-]+/dist/(?:css|js)/[A-Za-z0-9_.-]+\.bundle\.[A-Za-z0-9_-]+\.(?:css|js))",
    text,
)))

if not refs:
    print("[asset-check] no hashed bundle references found in sites/assets/assets.json", file=sys.stderr)
    sys.exit(1)

missing = [ref for ref in refs if not (assets / ref).is_file()]
if missing:
    print("[asset-check] manifest references missing files:", file=sys.stderr)
    for ref in missing[:20]:
        print(f"  /assets/{ref}", file=sys.stderr)
    if len(missing) > 20:
        print(f"  ... and {len(missing) - 20} more", file=sys.stderr)
    sys.exit(1)

print(f"[asset-check] OK: {len(refs)} manifest bundle references exist")
PY
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
  FORCE_MATERIALIZE=1 bash /home/frappe/frappe-bench/materialize-assets.sh \
    || echo "materialize-assets.sh could not sync baked manifests; rebuilding from cached dist..."
  bash /home/frappe/frappe-bench/sync-assets-manifest.sh 2>/dev/null \
    || { rm -f sites/assets/*.json; bench build --production --using-cached; }
'

if ! verify_assets_manifest backend; then
  echo "assets.json is stale or incomplete; rebuilding manifest from cached dist..."
  compose exec backend bash -c '
    set -euo pipefail
    cd /home/frappe/frappe-bench
    rm -f sites/assets/*.json
    bench build --production --using-cached
    FORCE_MATERIALIZE=1 bash /home/frappe/frappe-bench/materialize-assets.sh \
      || bash /home/frappe/frappe-bench/sync-assets-manifest.sh
  '
  verify_assets_manifest backend
fi

if [[ "${SKIP_MIGRATE}" -eq 0 ]]; then
  # Workers/scheduler query DocType while migrate ALTERs it → metadata lock wait.
  echo "Stopping workers before migrate..."
  compose stop queue-short queue-long scheduler 2>/dev/null || true
  migrate_failed=0
  echo "Running migrate on ${SITE}..."
  compose exec backend bench --site "${SITE}" migrate || migrate_failed=1
  echo "Starting workers after migrate..."
  compose start queue-short queue-long scheduler 2>/dev/null || true
  if [[ "${migrate_failed}" -ne 0 ]]; then
    exit 1
  fi
else
  echo "Skipping migrate (--skip-migrate)."
fi

echo "Clearing cache..."
compose exec backend bench --site "${SITE}" clear-cache
compose exec backend bench --site "${SITE}" clear-website-cache

echo "Restarting frontend..."
compose restart frontend

echo ""
echo "Asset check (frontend volume):"
if ! verify_assets_manifest frontend; then
  echo "ERROR: frontend cannot serve one or more bundles referenced by sites/assets/assets.json." >&2
  echo "Try:" >&2
  echo "  ./nando-deployment/setup-assets.sh ${ENV_FILE}" >&2
  exit 1
fi

echo ""
echo "Deploy complete."
echo "  Site: ${SITE}"
echo "  Compose: ${COMPOSE_FILE_OUTPUT}"
echo ""
compose ps
