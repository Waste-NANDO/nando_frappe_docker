#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/erpnext.yaml"
SITE="apps.internal.nandoai.com"
BACKUP_BASE="$SCRIPT_DIR/backups"
BACKUP_DIR="$BACKUP_BASE/$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS=7

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: Resolved compose file not found at $COMPOSE_FILE"
  echo "Run the generate command first (see DEPLOYMENT.md Step 7)"
  exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting backup..."

docker compose --project-name erpnext -f "$COMPOSE_FILE" exec -T backend \
  bench --site "$SITE" backup --with-files

mkdir -p "$BACKUP_DIR"
CONTAINER_ID=$(docker compose --project-name erpnext -f "$COMPOSE_FILE" ps -q backend)
docker cp "$CONTAINER_ID:/home/frappe/frappe-bench/sites/$SITE/private/backups/." "$BACKUP_DIR/"

echo "$(date '+%Y-%m-%d %H:%M:%S') Backup saved to: $BACKUP_DIR"
echo "Contents:"
ls -lh "$BACKUP_DIR/"

# Retain only last N days of backups
DELETED=$(find "$BACKUP_BASE/" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -not -path "$BACKUP_BASE/" -print)
if [ -n "$DELETED" ]; then
  echo "Cleaning up backups older than $RETENTION_DAYS days:"
  echo "$DELETED"
  find "$BACKUP_BASE/" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -not -path "$BACKUP_BASE/" -exec rm -rf {} +
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Backup complete."
