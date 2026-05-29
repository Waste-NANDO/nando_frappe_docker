#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
FETCH_SCRIPT="${SCRIPT_DIR}/fetch-custom-app.sh"
LOCAL_APP_DIR="${SCRIPT_DIR}/custom-app-src"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ -z "${ERPNEXT_VERSION:-}" ]]; then
  echo "ERPNEXT_VERSION must be set in ${ENV_FILE}" >&2
  exit 1
fi

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-erpnext}"
COMPOSE_FILE_OUTPUT="${COMPOSE_FILE_OUTPUT:-${SCRIPT_DIR}/erpnext.yaml}"
if [[ "${COMPOSE_FILE_OUTPUT}" != /* ]]; then
  COMPOSE_FILE_OUTPUT="${REPO_ROOT}/${COMPOSE_FILE_OUTPUT}"
fi

INCLUDE_CUSTOM_APP="${INCLUDE_CUSTOM_APP:-yes}"
CUSTOM_APP_REPO="${CUSTOM_APP_REPO:-git@github.com:Waste-NANDO/nando-erpnext-module.git}"
CUSTOM_APP_BRANCH="${CUSTOM_APP_BRANCH:-}"
CUSTOM_IMAGE="${CUSTOM_IMAGE:-nando-erpnext-custom}"
CUSTOM_TAG="${CUSTOM_TAG:-${ERPNEXT_VERSION}-custom}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-${ERPNEXT_VERSION}}"

render_compose() {
  docker compose --project-name "${COMPOSE_PROJECT_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${REPO_ROOT}/compose.yaml" \
    -f "${REPO_ROOT}/overrides/compose.redis.yaml" \
    -f "${REPO_ROOT}/overrides/compose.mariadb.yaml" \
    -f "${SCRIPT_DIR}/compose.custom-tls.yaml" \
    -f "${SCRIPT_DIR}/compose.backup.yaml" \
    config > "${COMPOSE_FILE_OUTPUT}"
}

if include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
  if [[ ! -x "${FETCH_SCRIPT}" ]]; then
    echo "Fetch script is missing or not executable: ${FETCH_SCRIPT}" >&2
    exit 1
  fi

  "${FETCH_SCRIPT}" "${ENV_FILE}"

  if [[ ! -d "${LOCAL_APP_DIR}/.git" ]]; then
    echo "Local custom app checkout is missing: ${LOCAL_APP_DIR}" >&2
    exit 1
  fi

  apps_json="$(mktemp)"
  trap 'rm -f "${apps_json}"' EXIT

  custom_branch_line=""
  if [[ -n "${CUSTOM_APP_BRANCH}" ]]; then
    custom_branch_line=$',\n    "branch": "'"${CUSTOM_APP_BRANCH}"'"'
  fi

  cat > "${apps_json}" <<EOF
[
  {
    "url": "https://github.com/frappe/erpnext.git",
    "branch": "${ERPNEXT_VERSION}"
  },
  {
    "url": "file:///opt/frappe/custom-app-src"${custom_branch_line}
  }
]
EOF

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
  echo "INCLUDE_CUSTOM_APP=${INCLUDE_CUSTOM_APP} — skipping fetch and image build."
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
  echo "CUSTOM_APP_REPO=${CUSTOM_APP_REPO}"
  if [[ -n "${CUSTOM_APP_BRANCH}" ]]; then
    echo "CUSTOM_APP_BRANCH=${CUSTOM_APP_BRANCH}"
  fi
  cat <<'EOF'

Then:
  1. Redeploy the stack.
  2. Run `bench --site <site> install-app <app_name>` once if the app is not installed yet.
  3. Run `bench --site <site> migrate` after later app updates.
EOF
else
  cat <<'EOF'

Then:
  1. Redeploy the stack.
  2. Create the site with `bench new-site` if this is a new environment.
EOF
fi
