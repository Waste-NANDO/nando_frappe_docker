#!/usr/bin/env bash
# Download a prod GCS backup object and restore it onto a docker stack.
# Usage:
#   ./refresh-from-gcs.sh --target dev --object nando-erp-main/v16.5.0/TS/xxx-database.sql.gz
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

TARGET="dev"
OBJECT=""
WITH_FILES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --object) OBJECT="${2:-}"; shift 2 ;;
    --with-files) WITH_FILES=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${OBJECT}" ]]; then
  echo "--object is required (GCS object path under the bucket)" >&2
  exit 1
fi

case "${TARGET}" in
  dev) ENV_FILE="${SCRIPT_DIR}/erpnext-dev.env" ;;
  quality) ENV_FILE="${SCRIPT_DIR}/erpnext-quality.env" ;;
  main|prod) ENV_FILE="${SCRIPT_DIR}/erpnext-main.env" ;;
  *) echo "target must be dev|quality|main" >&2; exit 1 ;;
esac

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a
source_versions_env "${SCRIPT_DIR}"

REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE_OUTPUT}"
if [[ "${COMPOSE_FILE}" != /* ]]; then
  COMPOSE_FILE="${REPO_ROOT}/${COMPOSE_FILE}"
fi
SITE="${FRAPPE_SITE_NAME_HEADER:-apps.internal.nandoai.com}"
BUCKET="${GCS_BUCKET:-nando-it-backups}"

compose() {
  docker compose --project-name "${COMPOSE_PROJECT_NAME}" \
    --project-directory "${REPO_ROOT}" \
    -f "${COMPOSE_FILE}" "$@"
}

WORKDIR="$(mktemp -d /tmp/nando-refresh-XXXXXX)"
echo "Work dir: ${WORKDIR}"
echo "Downloading gs://${BUCKET}/${OBJECT}"

# Prefer backup container (has GCS key + google-cloud-storage)
compose exec -T backup bash -lc "
  set -euo pipefail
  pip install -q google-cloud-storage 2>/dev/null || true
  python3 - <<PY
from google.cloud import storage
from pathlib import Path
client = storage.Client.from_service_account_json('/home/frappe/gcs-key.json')
bucket = client.bucket('${BUCKET}')
blob = bucket.blob('${OBJECT}')
dest = Path('/tmp/restore-db.sql.gz')
blob.download_to_filename(dest)
print(dest, dest.stat().st_size)
PY
"

compose cp backup:/tmp/restore-db.sql.gz "${WORKDIR}/database.sql.gz"
compose cp "${WORKDIR}/database.sql.gz" "backend:/tmp/database.sql.gz"

echo "Stopping workers before restore..."
compose stop queue-short queue-long scheduler 2>/dev/null || true

echo "Restoring database on ${SITE}..."
compose exec -T backend bench --site "${SITE}" restore /tmp/database.sql.gz --force

if [[ "${WITH_FILES}" -eq 1 ]]; then
  echo "NOTE: file restore not automated here; copy public/private from backup tarball if needed."
fi

compose start queue-short queue-long scheduler 2>/dev/null || true
echo "Restore complete. Sanitize + migrate via: nando-erp refresh (continuation) or bench migrate."
