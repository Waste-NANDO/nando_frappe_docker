#!/usr/bin/env bash
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

  docker buildx build \
    --load \
    --build-arg FRAPPE_PATH="https://github.com/frappe/frappe" \
    --build-arg FRAPPE_BRANCH="${FRAPPE_BRANCH}" \
    --build-arg APPS_JSON_BASE64="${APPS_JSON_BASE64}" \
    --tag "${CUSTOM_IMAGE}:${CUSTOM_TAG}" \
    --file "${REPO_ROOT}/images/layered/Containerfile" \
    "${REPO_ROOT}"

  echo "Built image: ${CUSTOM_IMAGE}:${CUSTOM_TAG}"
else
  echo "INCLUDE_CUSTOM_APP=${INCLUDE_CUSTOM_APP}, INCLUDE_HRMS=${INCLUDE_HRMS} — skipping image build."
  echo "Using image: ${CUSTOM_IMAGE:-frappe/erpnext}:${CUSTOM_TAG:-${ERPNEXT_VERSION}}"
fi

render_compose

cat <<EOF

Rendered compose file: ${COMPOSE_FILE_OUTPUT}
Compose project: ${COMPOSE_PROJECT_NAME}

If these lines are not already present in ${ENV_FILE}, add them before regenerating compose:
CUSTOM_IMAGE=${CUSTOM_IMAGE:-frappe/erpnext}
CUSTOM_TAG=${CUSTOM_TAG:-${ERPNEXT_VERSION}}
PULL_POLICY=${PULL_POLICY:-missing}
EOF

if include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
  echo "CUSTOM_APP_KEYS=${CUSTOM_APP_KEYS:-${CUSTOM_APP_NAME:-nando_fulfillment}}"
  read -r -a app_keys <<< "$(resolve_custom_app_keys)"
  for key in "${app_keys[@]}"; do
    key="$(echo "${key}" | xargs)"
    [[ -z "${key}" ]] && continue
    prefix="$(custom_app_env_prefix "${key}")"
    repo_var="${prefix}_REPO"
    branch_var="${prefix}_BRANCH"
    if [[ -n "${!repo_var:-}" ]]; then
      echo "${repo_var}=${!repo_var}"
    fi
    if [[ -n "${!branch_var:-}" ]]; then
      echo "${branch_var}=${!branch_var}"
    fi
  done
fi

if include_hrms_enabled "${INCLUDE_HRMS}"; then
  echo "INCLUDE_HRMS=yes"
  echo "HRMS_BRANCH=${HRMS_BRANCH}"
fi

if should_build_image; then
  cat <<'EOF'

Then:
  1. Redeploy the stack.
  2. Install apps on the site if needed (see below).
  3. Run `bench --site <site> migrate` after app updates.
EOF
  if include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
    read -r -a install_apps <<< "$(resolve_site_install_apps)"
    install_list=""
    for app in "${install_apps[@]}"; do
      app="$(echo "${app}" | xargs)"
      [[ -z "${app}" ]] && continue
      install_list="${install_list} ${app}"
    done
    if [[ -n "${install_list}" ]]; then
      echo "     - bench --site <site> install-app${install_list}"
    fi
  fi
  if include_hrms_enabled "${INCLUDE_HRMS}"; then
    echo '     - bench --site <site> install-app hrms'
  fi
else
  cat <<'EOF'

Then:
  1. Redeploy the stack.
  2. Create the site with `bench new-site` if this is a new environment.
EOF
fi
