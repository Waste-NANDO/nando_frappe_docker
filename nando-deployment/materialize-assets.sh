#!/usr/bin/env bash
# Copy app public/ trees (including dist/) into sites/assets on the shared volume.
# Symlinks under sites/assets only work in the container that ran bench build; nginx
# (frontend) needs real files on the volume. Run after bench build or on every deploy.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-/home/frappe/frappe-bench}"
ASSETS="${BENCH_ROOT}/sites/assets"
APPS="${BENCH_ROOT}/apps"
BAKED="${BENCH_ROOT}/.baked-assets"
FORCE_MATERIALIZE="${FORCE_MATERIALIZE:-0}"
MANIFEST_SYNC_NEEDED=0

mkdir -p "${ASSETS}"

if [[ "${FORCE_MATERIALIZE}" = "1" ]]; then
  shopt -s nullglob
  rm -f "${ASSETS}"/*.json
  shopt -u nullglob
  MANIFEST_SYNC_NEEDED=1
fi

resolve_public_dir() {
  local app_path="$1"
  local app="$2"
  local canonical="${app_path}/${app}/public"

  if [[ -d "${canonical}" ]]; then
    echo "${canonical}"
    return 0
  fi

  find "${app_path}" -maxdepth 3 -type d -name public 2>/dev/null | head -1
}

sync_assets_manifest() {
  if [[ -d "${BAKED}" ]]; then
    shopt -s nullglob
    local manifests=("${BAKED}"/*.json)
    shopt -u nullglob
    if [[ "${#manifests[@]}" -gt 0 ]]; then
      for manifest in "${manifests[@]}"; do
        echo "[materialize-assets] manifest $(basename "${manifest}") <- ${manifest}"
        cp -a "${manifest}" "${ASSETS}/$(basename "${manifest}")"
      done
      return 0
    fi
    echo "[materialize-assets] baked manifests directory empty"
  else
    echo "[materialize-assets] no baked manifests at ${BAKED}"
  fi

  echo "[materialize-assets] refreshing assets.json (bench build --production --using-cached)..."
  cd "${BENCH_ROOT}"
  bench build --production --using-cached
}

for app_path in "${APPS}"/*; do
  [[ -d "${app_path}" ]] || continue
  app=$(basename "${app_path}")
  public="$(resolve_public_dir "${app_path}" "${app}")"
  [[ -n "${public}" && -d "${public}" ]] || continue

  dest="${ASSETS}/${app}"
  needs_copy=0

  if [[ "${FORCE_MATERIALIZE}" = "1" ]]; then
    needs_copy=1
  elif [[ -L "${dest}" ]]; then
    needs_copy=1
  elif [[ ! -e "${dest}" ]]; then
    needs_copy=1
  elif [[ ! -d "${dest}/dist" ]] && [[ -d "${public}/dist" ]]; then
    needs_copy=1
  elif [[ -d "${public}/dist" && -d "${dest}/dist" ]] && \
      [[ -n "$(find "${public}/dist" -type f -newer "${dest}/dist" -print -quit 2>/dev/null)" ]]; then
    needs_copy=1
  fi

  if [[ "${needs_copy}" -eq 1 ]]; then
    echo "[materialize-assets] ${app} <- ${public}"
    rm -rf "${dest}"
    mkdir -p "${dest}"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --delete \
        --exclude node_modules \
        --exclude .git \
        "${public}/" "${dest}/"
    else
      cp -a "${public}/." "${dest}/"
      rm -rf "${dest}/node_modules"
    fi
    [[ -L "${dest}/node_modules" ]] && rm -f "${dest}/node_modules"
    MANIFEST_SYNC_NEEDED=1
  else
    echo "[materialize-assets] ${app} OK (skip)"
  fi
done

# Code/Text Editor fields load ace.js from sites/assets/frappe/node_modules/ace-builds.
# The public/ copy above excludes node_modules; nginx (frontend) needs real files on the volume.
materialize_ace_builds() {
  local ace_src=""
  for candidate in \
    "${APPS}/frappe/node_modules/ace-builds" \
    "${APPS}/frappe/frappe/node_modules/ace-builds"; do
    if [[ -d "${candidate}" ]]; then
      ace_src="${candidate}"
      break
    fi
  done
  if [[ -z "${ace_src}" ]]; then
    echo "[materialize-assets] ace-builds not found (skip)"
    return 0
  fi

  local ace_dest="${ASSETS}/frappe/node_modules/ace-builds"
  echo "[materialize-assets] frappe/node_modules/ace-builds <- ${ace_src}"
  mkdir -p "${ASSETS}/frappe/node_modules"
  rm -rf "${ace_dest}"
  cp -a "${ace_src}" "${ace_dest}"
}

materialize_ace_builds

if [[ "${MANIFEST_SYNC_NEEDED}" -eq 1 ]] || [[ ! -f "${ASSETS}/assets.json" ]]; then
  sync_assets_manifest
fi

echo "[materialize-assets] Done"
