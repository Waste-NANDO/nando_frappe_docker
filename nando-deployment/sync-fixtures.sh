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
DO_COMMIT=0
DO_PUSH=0
APPS=()

usage() {
  cat <<EOF
Usage: $0 --from <dev|main> --to <dev|main> [--apply] [--commit] [--push] [--force-update] [app ...]

Compares live Desk exports (not git). Git is the history ledger on main/master.

Default: export both sites, print missing/conflict report, write /tmp/fixture-sync-*.
  --apply         import missing docs onto the live dest site (force=False).
  --force-update  also import conflicting docs from source onto dest (force=True).
  --commit        after apply, re-export dest and commit fixtures on the app's
                  main/master branch (history). Does not commit onto git \`dev\`.
  --push          git push after --commit.

Routine deploy-stack migrate is the wrong apply path while both sites are edited in Desk.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="${2:-}"; shift 2 ;;
    --to) TO="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --commit) DO_COMMIT=1; shift ;;
    --push) DO_PUSH=1; shift ;;
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
if [[ "${DO_COMMIT}" -eq 1 && "${APPLY}" -eq 0 ]]; then
  echo "--commit requires --apply (commit the dest site after import)." >&2
  exit 1
fi
if [[ "${DO_PUSH}" -eq 1 && "${DO_COMMIT}" -eq 0 ]]; then
  echo "--push requires --commit" >&2
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

import_fixture_dir() {
  local side="$1"
  local app="$2"
  local host_dir="$3"
  local force="$4"
  if [[ -z "$(find "${host_dir}" -name '*.json' -print -quit 2>/dev/null)" ]]; then
    return 0
  fi
  compose_for "${side}" exec -T backend mkdir -p "/tmp/fixture-import/${app}"
  compose_for "${side}" cp "${host_dir}" "backend:/tmp/fixture-import/${app}-in"
  compose_for "${side}" exec -T backend bench --site "${SITE}" console <<PY
from pathlib import Path
from frappe.modules.import_file import import_file_by_path
root = Path("/tmp/fixture-import/${app}-in")
force = ${force}
for path in sorted(root.rglob("*.json")):
    print("import", path, "force", force)
    import_file_by_path(str(path), force=force)
frappe.db.commit()
exit()
PY
}

commit_dest_snapshot() {
  local app="$1"
  local snapshot_dir="$2"
  local git_fx repo
  git_fx="$(host_git_fixtures "${app}")"
  mkdir -p "${git_fx}"
  rsync -rl --exclude '.gitkeep' "${snapshot_dir}/" "${git_fx}/"
  repo="${SCRIPT_DIR}/custom-apps/${app}"
  git -C "${repo}" add -- "${git_fx#"${repo}/"}" || git -C "${repo}" add -A
  if git -C "${repo}" diff --cached --quiet; then
    echo "[git] ${app}: no fixture changes to commit"
    return 0
  fi
  git -C "${repo}" commit -m "fixtures: sync ${FROM} → ${TO} (${app})"
  if [[ "${DO_PUSH}" -eq 1 ]]; then
    git -C "${repo}" push origin HEAD
  else
    echo "[git] ${app}: committed on $(git -C "${repo}" branch --show-current). Push when ready."
  fi
}

MERGE_FLAGS=()
if [[ "${FORCE_UPDATE}" -eq 1 ]]; then
  MERGE_FLAGS+=(--force-update)
fi

if [[ "${DO_COMMIT}" -eq 1 ]]; then
  echo "[git] fetch main/master checkouts for history commits"
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
  changed_dir="${WORKDIR}/${app}/changed"
  mkdir -p "${src_dir}" "${dest_dir}" "${merged_dir}" "${missing_dir}" "${changed_dir}"

  export_site_fixtures "${FROM}" "${app}" "${src_dir}"
  export_site_fixtures "${TO}" "${app}" "${dest_dir}"

  python3 "${SCRIPT_DIR}/merge-fixtures.py" \
    --source "${src_dir}" \
    --dest "${dest_dir}" \
    --merged-out "${merged_dir}" \
    --missing-out "${missing_dir}" \
    --changed-out "${changed_dir}" \
    "${MERGE_FLAGS[@]+"${MERGE_FLAGS[@]}"}"

  if [[ "${APPLY}" -eq 0 ]]; then
    echo "Dry run. Inspect ${merged_dir} / ${missing_dir}"
    echo "Re-run with --apply to import onto live ${TO}."
    echo "Add --commit to record dest fixtures on git main/master after apply."
    continue
  fi

  echo "[${TO}] import missing docs onto live site"
  import_fixture_dir "${TO}" "${app}" "${missing_dir}" False
  if [[ "${FORCE_UPDATE}" -eq 1 ]]; then
    echo "[${TO}] import conflicting docs from ${FROM} (force=True)"
    import_fixture_dir "${TO}" "${app}" "${changed_dir}" True
  fi
  compose_for "${TO}" exec -T backend bench --site "${SITE}" clear-cache

  if [[ "${DO_COMMIT}" -eq 1 ]]; then
    snapshot_dir="${WORKDIR}/${app}/dest-after"
    mkdir -p "${snapshot_dir}"
    export_site_fixtures "${TO}" "${app}" "${snapshot_dir}"
    commit_dest_snapshot "${app}" "${snapshot_dir}"
  fi
done

echo ""
echo "Done. Work dir kept at ${WORKDIR}"
echo "Conflicts were left on dest unless you passed --force-update."
echo "Do not use deploy-stack migrate to apply Desk fixtures while both sites are edited in the UI."
