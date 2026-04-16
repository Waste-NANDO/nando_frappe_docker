#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${1:-${SCRIPT_DIR}/erpnext.env}"
FETCH_SCRIPT="${SCRIPT_DIR}/fetch-custom-app.sh"
LOCAL_APP_DIR="${SCRIPT_DIR}/custom-app-src"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Env file not found: ${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ -z "${ERPNEXT_VERSION:-}" ]]; then
  echo "ERPNEXT_VERSION must be set in ${ENV_FILE}" >&2
  exit 1
fi

CUSTOM_APP_REPO="${CUSTOM_APP_REPO:-git@github.com:Waste-NANDO/nando-erpnext-module.git}"
CUSTOM_APP_BRANCH="${CUSTOM_APP_BRANCH:-}"
CUSTOM_IMAGE="${CUSTOM_IMAGE:-nando-erpnext-custom}"
CUSTOM_TAG="${CUSTOM_TAG:-${ERPNEXT_VERSION}-custom}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-${ERPNEXT_VERSION}}"

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

cat <<EOF

Built image: ${CUSTOM_IMAGE}:${CUSTOM_TAG}

If these lines are not already present in ${ENV_FILE}, add them before regenerating compose:
CUSTOM_IMAGE=${CUSTOM_IMAGE}
CUSTOM_TAG=${CUSTOM_TAG}
PULL_POLICY=never
CUSTOM_APP_REPO=${CUSTOM_APP_REPO}
EOF

if [[ -n "${CUSTOM_APP_BRANCH}" ]]; then
  echo "CUSTOM_APP_BRANCH=${CUSTOM_APP_BRANCH}"
fi

cat <<'EOF'

Then:
  1. Regenerate the resolved compose file.
  2. Redeploy the stack.
  3. Run `bench --site <site> install-app <app_name>` once if the app is not installed yet.
  4. Run `bench --site <site> migrate` after later app updates.
EOF
