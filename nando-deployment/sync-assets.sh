#!/usr/bin/env bash
# Force-copy image assets to sites/assets on the shared volume (fix Desk 404 on bundles).
# Safe to run anytime; no bench build unless --full.
#
# Usage:
#   ./sync-assets.sh nando-deployment/erpnext-dev.env
#   ./sync-assets.sh nando-deployment/erpnext-dev.env --full
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/setup-assets.sh" "$@"
