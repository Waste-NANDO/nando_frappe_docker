#!/usr/bin/env bash
# Promote missing fixtures from live dev (:3003) into the main git checkout.
# Does not overwrite docs that already exist on main unless --force-update.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/sync-fixtures.sh" --from dev --to main "$@"
