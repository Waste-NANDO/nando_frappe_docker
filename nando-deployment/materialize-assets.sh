#!/usr/bin/env bash
# Copy app public/ trees (including dist/) into sites/assets on the shared volume.
# Symlinks under sites/assets only work in the container that ran bench build; nginx
# (frontend) needs real files on the volume. Run after bench build or on every deploy.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-/home/frappe/frappe-bench}"
ASSETS="${BENCH_ROOT}/sites/assets"
APPS="${BENCH_ROOT}/apps"

mkdir -p "${ASSETS}"

for app_path in "${APPS}"/*; do
  [[ -d "${app_path}" ]] || continue
  app=$(basename "${app_path}")
  # maxdepth avoids scanning node_modules under app trees (can hang for many minutes)
  public=$(find "${app_path}" -maxdepth 3 -type d -name public 2>/dev/null | head -1)
  [[ -n "${public}" && -d "${public}" ]] || continue

  dest="${ASSETS}/${app}"
  needs_copy=0

  if [[ -L "${dest}" ]]; then
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
  else
    echo "[materialize-assets] ${app} OK (skip)"
  fi
done

echo "[materialize-assets] Done"
