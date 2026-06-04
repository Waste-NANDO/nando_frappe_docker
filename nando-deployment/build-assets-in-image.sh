#!/usr/bin/env bash
# Run during docker image build (frappe/build stage).
# HRMS PWA/roster (yarn vite via --run-build-command) often fails in Docker;
# we build HRMS desk bundles via esbuild only. Set BUILD_HRMS_FULL=1 to attempt PWA too.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-/home/frappe/frappe-bench}"
BENCH_BUILD_NODE_MEMORY_MB="${BENCH_BUILD_NODE_MEMORY_MB:-6144}"
BUILD_HRMS_FULL="${BUILD_HRMS_FULL:-0}"

export NODE_OPTIONS="--max-old-space-size=${BENCH_BUILD_NODE_MEMORY_MB}"

cd "${BENCH_ROOT}"

build_app_production() {
  local app="$1"
  if [[ ! -d "apps/${app}" ]]; then
    echo "[build-assets] skip missing app: ${app}"
    return 0
  fi
  echo "[build-assets] bench build --production --app ${app}"
  bench build --production --app "${app}"
}

# Order: core apps first, then everything else except hrms (handled separately).
for app in frappe erpnext; do
  build_app_production "${app}"
done

if [[ -d apps/hrms ]]; then
  if [[ "${BUILD_HRMS_FULL}" = "1" ]]; then
    echo "[build-assets] HRMS full build (includes PWA/roster — may fail in Docker)"
    build_app_production hrms
  else
    echo "[build-assets] HRMS esbuild only (skipping --run-build-command / PWA/roster)"
    cd apps/frappe
    yarn run production --apps hrms
    cd "${BENCH_ROOT}"
  fi
fi

for app_path in apps/*; do
  [[ -d "${app_path}" ]] || continue
  app="$(basename "${app_path}")"
  case "${app}" in
    frappe | erpnext | hrms) continue ;;
  esac
  build_app_production "${app}"
done

echo "[build-assets] Done"

# Manifest on sites/assets/ (assets.json) must match dist/ hashes. The sites volume
# persists across deploys and can keep stale manifests; bake a copy outside sites/.
BAKED="${BENCH_ROOT}/.baked-assets"
mkdir -p "${BAKED}"
shopt -s nullglob
for manifest in "${BENCH_ROOT}/sites/assets/"*.json; do
  cp -a "${manifest}" "${BAKED}/$(basename "${manifest}")"
  echo "[build-assets] baked manifest $(basename "${manifest}")"
done
shopt -u nullglob
