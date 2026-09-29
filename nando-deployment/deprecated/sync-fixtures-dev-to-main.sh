#!/usr/bin/env bash
# DEPRECATED — see deprecated/README.md. Prefer nando-erp capture / deploy / promote.
# Sync missing Desk fixtures from live dev (:3003) onto live main (:3000).
# Git history: add --commit (records dest snapshot on app main/master).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/sync-fixtures.sh" --from dev --to main "$@"
