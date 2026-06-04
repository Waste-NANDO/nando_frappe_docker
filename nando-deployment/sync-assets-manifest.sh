#!/usr/bin/env bash
# Regenerate sites/assets/assets.json from dist/ already in apps/ (fast; no full yarn build).
# Run after materialize when HTML references bundle hashes that do not exist on the volume.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-/home/frappe/frappe-bench}"
ASSETS="${BENCH_ROOT}/sites/assets"

cd "${BENCH_ROOT}"

shopt -s nullglob
rm -f "${ASSETS}"/*.json
shopt -u nullglob

echo "[sync-assets-manifest] bench build --production --using-cached"
bench build --production --using-cached
echo "[sync-assets-manifest] Done"
