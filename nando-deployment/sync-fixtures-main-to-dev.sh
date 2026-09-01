#!/usr/bin/env bash
# Copy missing fixtures from live main (:3000) onto the live dev site.
# Does not write fixtures onto the git `dev` branch (that branch stays empty).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/sync-fixtures.sh" --from main --to dev "$@"
