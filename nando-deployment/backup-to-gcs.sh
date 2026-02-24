#!/bin/bash
set -euo pipefail

: "${SITE_NAME:?SITE_NAME is required}"
: "${GCS_BUCKET:?GCS_BUCKET is required}"
GCS_KEY_FILE="${GCS_KEY_FILE:-/home/frappe/gcs-key.json}"
BACKUP_KEEP="${BACKUP_KEEP:-10}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-604800}"

BENCH_DIR="/home/frappe/frappe-bench"
BACKUP_DIR="$BENCH_DIR/sites/$SITE_NAME/private/backups"
PY="$BENCH_DIR/env/bin/python"

cd "$BENCH_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [backup] $*"; }

log "Installing GCS dependencies..."
"$BENCH_DIR/env/bin/pip" install --quiet google-cloud-storage

log "Backup service started"
log "  Site:     $SITE_NAME"
log "  Bucket:   gs://$GCS_BUCKET"
log "  Keep:     $BACKUP_KEEP backups"
log "  Interval: $((INTERVAL / 86400))d $((INTERVAL % 86400 / 3600))h"

while true; do
  log "Running bench backup..."
  STARTED_AT=$(date +%s)

  if ! bench --site "$SITE_NAME" backup --with-files; then
    log "ERROR: bench backup failed. Retrying in 1 hour."
    sleep 3600
    continue
  fi

  TIMESTAMP=$(date +%Y%m%d_%H%M%S)

  log "Uploading to gs://$GCS_BUCKET/$SITE_NAME/$TIMESTAMP/ ..."
  if ! "$PY" /home/frappe/upload-to-gcs.py \
    --site "$SITE_NAME" \
    --bucket "$GCS_BUCKET" \
    --key-file "$GCS_KEY_FILE" \
    --timestamp "$TIMESTAMP" \
    --keep "$BACKUP_KEEP" \
    --backup-dir "$BACKUP_DIR" \
    --since "$STARTED_AT"; then
    log "ERROR: GCS upload failed. Will retry next cycle."
  fi

  log "Done. Next backup in $((INTERVAL / 86400))d $((INTERVAL % 86400 / 3600))h."
  sleep "$INTERVAL"
done
