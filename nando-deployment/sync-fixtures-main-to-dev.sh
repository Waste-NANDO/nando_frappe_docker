#!/usr/bin/env bash
# Sync missing Desk fixtures from live main (:3000) onto live dev (:3003).
# Git history: add --commit (records dest snapshot on app main/master, not git `dev`).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/sync-fixtures.sh" --from main --to dev "$@"
