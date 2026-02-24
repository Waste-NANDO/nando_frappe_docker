#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/erpnext.yaml"
SITE="apps.internal.nandoai.com"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_TMP="$(mktemp -d)"
# Required env vars — set before running, e.g.:
#   GCS_BUCKET=my-bucket GCS_KEY_FILE=/etc/gcs-key.json ./backup.sh
GCS_BUCKET="${GCS_BUCKET:?ERROR: GCS_BUCKET environment variable is not set}"
GCS_KEY_FILE="${GCS_KEY_FILE:?ERROR: GCS_KEY_FILE environment variable is not set}"
GCS_DEST="gs://$GCS_BUCKET/$SITE/$TIMESTAMP"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: Resolved compose file not found at $COMPOSE_FILE"
  echo "Run the generate command first (see DEPLOYMENT.md Step 7)"
  exit 1
fi

if [ ! -f "$GCS_KEY_FILE" ]; then
  echo "ERROR: GCS key file not found at $GCS_KEY_FILE"
  exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting backup..."

docker compose --project-name erpnext -f "$COMPOSE_FILE" exec -T backend \
  bench --site "$SITE" backup --with-files

CONTAINER_ID=$(docker compose --project-name erpnext -f "$COMPOSE_FILE" ps -q backend)
docker cp "$CONTAINER_ID:/home/frappe/frappe-bench/sites/$SITE/private/backups/." "$BACKUP_TMP/"

echo "$(date '+%Y-%m-%d %H:%M:%S') Uploading backup to $GCS_DEST ..."
docker run --rm \
  -v "$BACKUP_TMP:/backup:ro" \
  -v "$GCS_KEY_FILE:/key.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/key.json \
  google/cloud-sdk:slim \
  gsutil -m rsync -r /backup/ "$GCS_DEST/"

rm -rf "$BACKUP_TMP"
echo "$(date '+%Y-%m-%d %H:%M:%S') Backup complete. Files at: $GCS_DEST"
