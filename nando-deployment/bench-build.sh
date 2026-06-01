#!/usr/bin/env bash
# Run inside the backend container after app changes: rebuild bundles and copy to sites volume.
set -euo pipefail
bench build "$@"
/home/frappe/frappe-bench/materialize-assets.sh
