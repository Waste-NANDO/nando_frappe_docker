#!/usr/bin/env bash
# Align sites/assets/assets.json with hashed bundles already on the volume.
# Backend images have no node — do not call bench build here.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-/home/frappe/frappe-bench}"
REWRITE="${BENCH_ROOT}/rewrite-assets-manifest.py"

cd "${BENCH_ROOT}"

if [[ ! -f "${REWRITE}" ]]; then
  echo "[sync-assets-manifest] missing ${REWRITE}" >&2
  exit 1
fi

echo "[sync-assets-manifest] rewrite-assets-manifest.py"
python3 "${REWRITE}"
echo "[sync-assets-manifest] Done"
