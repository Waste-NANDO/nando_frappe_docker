#!/usr/bin/env bash
# Compare fixture JSON between stacks. Default is report-only.
# Adds missing docs; does not overwrite conflicts unless --force-update.
#
# Usage:
#   ./sync-fixtures.sh --from dev --to main [--apply] [--force-update] [app ...]
#   ./sync-fixtures.sh --from main --to dev [--apply] [--force-update] [app ...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

FROM=""
TO=""
APPLY=0
FORCE_UPDATE=0
APPS=()

usage() {
  cat <<EOF
Usage: $0 --from <dev|main> --to <dev|main> [--apply] [--force-update] [app ...]

Default: export both sides, print a missing/conflict report, write /tmp/fixture-sync-*.
  --apply         dest=main: write merged fixtures into custom-apps (git checkout).
                  dest=dev:  import missing docs onto the live dev site (force=False).
  --force-update  overwrite dest docs that already exist but differ (dangerous).

Does not git commit, push, rebuild, or migrate. Those stay manual.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="${2:-}"; shift 2 ;;
    --to) TO="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --force-update) FORCE_UPDATE=1; shift ;;
    -h | --help) usage; exit 0 ;;
    --*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *) APPS+=("$1"); shift ;;
  esac
done

if [[ "${FROM}" != "dev" && "${FROM}" != "main" ]]; then
  echo "--from must be dev or main" >&2
  usage >&2
  exit 1
fi
if [[ "${TO}" != "dev" && "${TO}" != "main" ]]; then
  echo "--to must be dev or main" >&2
  usage >&2
  exit 1
fi
if [[ "${FROM}" == "${TO}" ]]; then
  echo "--from and --to must differ" >&2
  exit 1
fi

stack_env() {
  case "$1" in
    dev) echo "${SCRIPT_DIR}/erpnext-dev.env" ;;
    main) echo "${SCRIPT_DIR}/erpnext-main.env" ;;
  esac
}

load_stack() {
  local side="$1"
  local env_file
  env_file="$(stack_env "${side}")"
  if [[ ! -f "${env_file}" ]]; then
    echo "Env file not found: ${env_file}" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "${env_file}"
  set +a
}

compose_for() {
  local side="$1"
  load_stack "${side}"
  local compose_file="${COMPOSE_FILE_OUTPUT:-}"
  if [[ "${compose_file}" != /* ]]; then
    compose_file="${REPO_ROOT}/${compose_file}"
  fi
  if [[ ! -f "${compose_file}" ]]; then
    echo "Compose file missing: ${compose_file}" >&2
    echo "Render it first: ./nando-deployment/render-compose.sh $(stack_env "${side}")" >&2
    exit 1
  fi
  docker compose --project-name "${COMPOSE_PROJECT_NAME}" \
    --project-directory "${REPO_ROOT}" \
    -f "${compose_file}" "$@"
}

SITE="apps.internal.nandoai.com"

if [[ ${#APPS[@]} -eq 0 ]]; then
  load_stack "${FROM}"
  read -r -a APPS <<< "$(resolve_custom_app_keys)"
fi
if [[ ${#APPS[@]} -eq 0 ]]; then
  echo "No apps to sync. Pass app names or set CUSTOM_APP_KEYS." >&2
  exit 1
fi

WORKDIR="$(mktemp -d /tmp/fixture-sync-${FROM}-to-${TO}-XXXXXX)"
echo "Work dir: ${WORKDIR}"
echo "Direction: ${FROM} → ${TO}"
echo "Apps: ${APPS[*]}"
if [[ "${FORCE_UPDATE}" -eq 1 ]]; then
  echo "WARNING: --force-update will overwrite dest docs that differ (this is how unique-index overwrites happen)."
fi
echo ""

container_fixtures() {
  local app="$1"
  echo "/home/frappe/frappe-bench/apps/${app}/${app}/fixtures"
}

host_git_fixtures() {
  local app="$1"
  local root="${SCRIPT_DIR}/custom-apps/${app}"
  if [[ -d "${root}/${app}/fixtures" ]]; then
    echo "${root}/${app}/fixtures"
  elif [[ -d "${root}/fixtures" ]]; then
    echo "${root}/fixtures"
  else
    mkdir -p "${root}/${app}/fixtures"
    echo "${root}/${app}/fixtures"
  fi
}

export_site_fixtures() {
  local side="$1"
  local app="$2"
  local dest="$3"
  local copied
  echo "[${side}] export-fixtures --app ${app}"
  compose_for "${side}" exec -T backend \
    bench --site "${SITE}" export-fixtures --app "${app}"
  mkdir -p "${dest}"
  copied="$(mktemp -d "${WORKDIR}/cp-${side}-${app}-XXXXXX")"
  if compose_for "${side}" cp \
    "backend:$(container_fixtures "${app}")" \
    "${copied}/fixtures"; then
    cp -a "${copied}/fixtures/." "${dest}/"
  else
    echo "No fixtures dir in ${side} container for ${app} (empty export is ok)."
  fi
}

MERGE_FLAGS=()
if [[ "${FORCE_UPDATE}" -eq 1 ]]; then
  MERGE_FLAGS+=(--force-update)
fi

if [[ "${TO}" == "main" ]]; then
  echo "[main] fetch git branches into custom-apps/"
  "${SCRIPT_DIR}/fetch-custom-app.sh" "$(stack_env main)"
fi

for app in "${APPS[@]}"; do
  app="$(echo "${app}" | xargs)"
  [[ -z "${app}" ]] && continue

  echo "══════════════════════════════════════════════════════════════"
  echo " App: ${app}"
  echo "══════════════════════════════════════════════════════════════"

  src_dir="${WORKDIR}/${app}/source"
  dest_dir="${WORKDIR}/${app}/dest"
  merged_dir="${WORKDIR}/${app}/merged"
  missing_dir="${WORKDIR}/${app}/missing"
  mkdir -p "${src_dir}" "${dest_dir}" "${merged_dir}" "${missing_dir}"

  export_site_fixtures "${FROM}" "${app}" "${src_dir}"

  if [[ "${TO}" == "main" ]]; then
    git_fx="$(host_git_fixtures "${app}")"
    if [[ -d "${git_fx}" ]]; then
      cp -a "${git_fx}/." "${dest_dir}/"
    fi
  else
    export_site_fixtures "${TO}" "${app}" "${dest_dir}"
  fi

  python3 "${SCRIPT_DIR}/merge-fixtures.py" \
    --source "${src_dir}" \
    --dest "${dest_dir}" \
    --merged-out "${merged_dir}" \
    --missing-out "${missing_dir}" \
    "${MERGE_FLAGS[@]+"${MERGE_FLAGS[@]}"}"

  if [[ "${APPLY}" -eq 0 ]]; then
    echo "Dry run. Inspect ${merged_dir} and ${missing_dir}"
    echo "Re-run with --apply to write/import."
    continue
  fi

  if [[ "${TO}" == "main" ]]; then
    git_fx="$(host_git_fixtures "${app}")"
    mkdir -p "${git_fx}"
    rsync -rl --exclude '.gitkeep' \
      "${merged_dir}/" "${git_fx}/"
    echo "Wrote merged fixtures → ${git_fx}"
    echo "Next:"
    echo "  cd ${SCRIPT_DIR}/custom-apps/${app}"
    echo "  git add -A && git status"
    echo "  git commit && git push origin HEAD"
    echo "  ./nando-deployment/build-custom-image.sh nando-deployment/erpnext-main.env"
    echo "  ./nando-deployment/deploy-stack.sh nando-deployment/erpnext-main.env"
  else
    if [[ -z "$(find "${missing_dir}" -name '*.json' -print -quit 2>/dev/null)" ]]; then
      echo "Nothing missing on dev; no import."
      continue
    fi
    compose_for dev exec -T backend mkdir -p "/tmp/fixture-import/${app}"
    compose_for dev cp "${missing_dir}" "backend:/tmp/fixture-import/${app}"
    compose_for dev exec -T backend bench --site "${SITE}" console <<PY
from pathlib import Path
from frappe.modules.import_file import import_file_by_path
root = Path("/tmp/fixture-import/${app}")
for path in sorted(root.rglob("*.json")):
    print("import", path)
    import_file_by_path(str(path), force=False)
frappe.db.commit()
print("imported missing fixtures for ${app}")
exit()
PY
    compose_for dev exec -T backend bench --site "${SITE}" clear-cache
    echo "Imported missing fixtures onto the live dev site."
  fi
done

echo ""
echo "Done. Work dir kept at ${WORKDIR}"
echo "Do not migrate main until you have reviewed conflicting DocTypes."
