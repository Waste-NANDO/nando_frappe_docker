#!/usr/bin/env bash
# Build only: fetch custom apps, docker build, render compose YAML.
# Does NOT start containers, migrate, or clear cache — use deploy-stack.sh for that.
#
# Usage:
#   ./build-custom-image.sh nando-deployment/erpnext-dev.env
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
FETCH_SCRIPT="${SCRIPT_DIR}/fetch-custom-app.sh"
LOCAL_APPS_DIR="${SCRIPT_DIR}/custom-apps"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ -z "${ERPNEXT_VERSION:-}" ]]; then
  echo "ERPNEXT_VERSION must be set in ${ENV_FILE}" >&2
  exit 1
fi

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-erpnext}"
COMPOSE_FILE_OUTPUT="${COMPOSE_FILE_OUTPUT:-${SCRIPT_DIR}/erpnext-dev.yaml}"
if [[ "${COMPOSE_FILE_OUTPUT}" != /* ]]; then
  COMPOSE_FILE_OUTPUT="${REPO_ROOT}/${COMPOSE_FILE_OUTPUT}"
fi

INCLUDE_CUSTOM_APP="${INCLUDE_CUSTOM_APP:-yes}"
INCLUDE_HRMS="${INCLUDE_HRMS:-no}"
HRMS_REPO="${HRMS_REPO:-https://github.com/frappe/hrms.git}"
HRMS_BRANCH="${HRMS_BRANCH:-version-16}"
CUSTOM_IMAGE="${CUSTOM_IMAGE:-nando-erpnext-custom}"
CUSTOM_TAG="${CUSTOM_TAG:-${ERPNEXT_VERSION}-custom}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
BUILD_ASSETS_IN_IMAGE="${BUILD_ASSETS_IN_IMAGE:-yes}"
BENCH_BUILD_NODE_MEMORY_MB="${BENCH_BUILD_NODE_MEMORY_MB:-6144}"
BUILD_HRMS_FULL="${BUILD_HRMS_FULL:-0}"

build_assets_arg=0
build_hrms_full_arg=0
if build_assets_in_image_enabled "${BUILD_ASSETS_IN_IMAGE}"; then
  build_assets_arg=1
fi
if build_assets_in_image_enabled "${BUILD_HRMS_FULL}"; then
  build_hrms_full_arg=1
fi

render_compose() {
  write_compose_output "${COMPOSE_FILE_OUTPUT}" \
    docker compose --project-name "${COMPOSE_PROJECT_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${REPO_ROOT}/compose.yaml" \
    -f "${REPO_ROOT}/overrides/compose.redis.yaml" \
    -f "${REPO_ROOT}/overrides/compose.mariadb.yaml" \
    -f "${SCRIPT_DIR}/compose.custom-tls.yaml" \
    -f "${SCRIPT_DIR}/compose.materialize.yaml" \
    -f "${SCRIPT_DIR}/compose.backup.yaml"
}

write_apps_json() {
  local outfile="$1"
  local first=1
  local key

  {
    echo '['
    echo '  {'
    echo '    "url": "https://github.com/frappe/erpnext.git",'
    echo "    \"branch\": \"${ERPNEXT_VERSION}\""
    echo -n '  }'
    first=0

    if include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
      read -r -a app_keys <<< "$(resolve_custom_app_keys)"
      for key in "${app_keys[@]}"; do
        key="$(echo "${key}" | xargs)"
        [[ -z "${key}" ]] && continue
        echo ','
        echo '  {'
        echo "    \"url\": \"file:///opt/frappe/custom-apps/${key}\""
        echo -n '  }'
      done
    fi

    if include_hrms_enabled "${INCLUDE_HRMS}"; then
      echo ','
      echo '  {'
      echo "    \"url\": \"${HRMS_REPO}\","
      echo "    \"branch\": \"${HRMS_BRANCH}\""
      echo -n '  }'
    fi

    echo ''
    echo ']'
  } > "${outfile}"
}

should_build_image() {
  include_custom_app_enabled "${INCLUDE_CUSTOM_APP}" || include_hrms_enabled "${INCLUDE_HRMS}"
}

if should_build_image; then
  if include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
    if [[ ! -x "${FETCH_SCRIPT}" ]]; then
      echo "Fetch script is missing or not executable: ${FETCH_SCRIPT}" >&2
      exit 1
    fi

    "${FETCH_SCRIPT}" "${ENV_FILE}"

    read -r -a app_keys <<< "$(resolve_custom_app_keys)"
    for key in "${app_keys[@]}"; do
      key="$(echo "${key}" | xargs)"
      [[ -z "${key}" ]] && continue
      if [[ ! -d "${LOCAL_APPS_DIR}/${key}/.git" ]]; then
        echo "Custom app checkout is missing: ${LOCAL_APPS_DIR}/${key}" >&2
        exit 1
      fi
    done
  fi

  apps_json="$(mktemp)"
  trap 'rm -f "${apps_json}"' EXIT

  write_apps_json "${apps_json}"

  APPS_JSON_BASE64="$(base64 < "${apps_json}" | tr -d '\n')"

  echo "Building image (BUILD_ASSETS_IN_IMAGE=${build_assets_arg}, node heap ${BENCH_BUILD_NODE_MEMORY_MB}MB)..."
  if [[ "${build_assets_arg}" -eq 1 ]]; then
    echo "Asset compile runs inside docker build — expect 10–20 minutes with HRMS."
    if [[ "${build_hrms_full_arg}" -eq 0 ]]; then
      echo "HRMS PWA/roster skipped in image (BUILD_HRMS_FULL=0); Desk HRMS bundles still built."
    fi
  fi

  docker buildx build \
    --load \
    --build-arg FRAPPE_PATH="https://github.com/frappe/frappe" \
    --build-arg FRAPPE_BRANCH="${FRAPPE_BRANCH}" \
    --build-arg APPS_JSON_BASE64="${APPS_JSON_BASE64}" \
    --build-arg BUILD_ASSETS_IN_IMAGE="${build_assets_arg}" \
    --build-arg BENCH_BUILD_NODE_MEMORY_MB="${BENCH_BUILD_NODE_MEMORY_MB}" \
    --build-arg BUILD_HRMS_FULL="${build_hrms_full_arg}" \
    --tag "${CUSTOM_IMAGE}:${CUSTOM_TAG}" \
    --file "${REPO_ROOT}/images/layered/Containerfile" \
    "${REPO_ROOT}"

  echo "Built image: ${CUSTOM_IMAGE}:${CUSTOM_TAG}"
else
  echo "INCLUDE_CUSTOM_APP=${INCLUDE_CUSTOM_APP}, INCLUDE_HRMS=${INCLUDE_HRMS} — skipping image build."
  echo "Using image: ${CUSTOM_IMAGE:-frappe/erpnext}:${CUSTOM_TAG:-${ERPNEXT_VERSION}}"
fi

render_compose

rel_env="${ENV_FILE}"
if [[ "${rel_env}" == "${REPO_ROOT}/"* ]]; then
  rel_env="${rel_env#"${REPO_ROOT}/"}"
fi

echo ""
echo "══════════════════════════════════════════════════════════════"
echo " BUILD COMPLETE"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "This script prepares the image and compose file. It does NOT"
echo "start containers, migrate, or clear cache."
echo ""

if should_build_image; then
  echo "Done:"
  if include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
    read -r -a app_keys <<< "$(resolve_custom_app_keys)"
    for key in "${app_keys[@]}"; do
      key="$(echo "${key}" | xargs)"
      [[ -z "${key}" ]] && continue
      prefix="$(custom_app_env_prefix "${key}")"
      branch_var="${prefix}_BRANCH"
      branch="${!branch_var:-default}"
      rev=""
      if [[ -d "${LOCAL_APPS_DIR}/${key}/.git" ]]; then
        rev="$(git -C "${LOCAL_APPS_DIR}/${key}" rev-parse --short HEAD 2>/dev/null || true)"
      fi
      echo "  • Fetched ${key} (branch ${branch}${rev:+, ${rev}})"
    done
  fi
  echo "  • Built image ${CUSTOM_IMAGE}:${CUSTOM_TAG}"
  if [[ "${build_assets_arg}" -eq 1 ]]; then
    echo "  • Compiled Desk assets inside the image (BUILD_ASSETS_IN_IMAGE=yes)"
  fi
else
  echo "Done:"
  echo "  • Skipped Docker build (INCLUDE_CUSTOM_APP/Hrms disabled)"
  echo "  • Using image ${CUSTOM_IMAGE:-frappe/erpnext}:${CUSTOM_TAG:-${ERPNEXT_VERSION}}"
fi

echo "  • Rendered compose → ${COMPOSE_FILE_OUTPUT}"
echo ""
echo "Next — deploy the running stack (no rebuild):"
echo "  ./nando-deployment/deploy-stack.sh ${rel_env}"
echo ""
echo "Or build again and deploy in one command:"
echo "  ./nando-deployment/deploy-stack.sh ${rel_env} --with-build"
echo ""
if include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
  read -r -a install_apps <<< "$(resolve_site_install_apps)"
  install_list=""
  for app in "${install_apps[@]}"; do
    app="$(echo "${app}" | xargs)"
    [[ -z "${app}" ]] && continue
    install_list="${install_list} ${app}"
  done
  if [[ -n "${install_list}" ]]; then
    echo "First-time site only (not part of build/deploy):"
    echo "  bench --site ${FRAPPE_SITE_NAME_HEADER:-<site>} install-app${install_list}"
    if include_hrms_enabled "${INCLUDE_HRMS}"; then
      echo "  bench --site ${FRAPPE_SITE_NAME_HEADER:-<site>} install-app hrms"
    fi
    echo ""
  fi
fi
