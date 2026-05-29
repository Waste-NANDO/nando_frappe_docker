#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
TARGET_DIR="${SCRIPT_DIR}/custom-app-src"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

INCLUDE_CUSTOM_APP="${INCLUDE_CUSTOM_APP:-yes}"
if ! include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
  echo "INCLUDE_CUSTOM_APP=${INCLUDE_CUSTOM_APP} — skipping custom app fetch (${ENV_FILE})."
  exit 0
fi

CUSTOM_APP_REPO="${CUSTOM_APP_REPO:-git@github.com:Waste-NANDO/nando-erpnext-module.git}"
CUSTOM_APP_BRANCH="${CUSTOM_APP_BRANCH:-}"

if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
  cat >&2 <<'EOF'
SSH agent not detected.

Start an agent, add the GitHub deploy key, and rerun:
  eval "$(ssh-agent -s)"
  ssh-add ~/.ssh/<github-key>
EOF
  exit 1
fi

if ! ssh-add -l >/dev/null 2>&1; then
  cat >&2 <<'EOF'
No SSH keys are currently loaded in the agent.

Load the GitHub deploy key, then rerun:
  ssh-add ~/.ssh/<github-key>
EOF
  exit 1
fi

if [[ -d "${TARGET_DIR}/.git" ]]; then
  current_remote="$(git -C "${TARGET_DIR}" remote get-url origin)"
  if [[ "${current_remote}" != "${CUSTOM_APP_REPO}" ]]; then
    cat >&2 <<EOF
Existing checkout uses a different remote:
  ${current_remote}

Expected:
  ${CUSTOM_APP_REPO}

Remove ${TARGET_DIR} if you want to replace it.
EOF
    exit 1
  fi

  git -C "${TARGET_DIR}" fetch --tags --prune origin

  if [[ -n "${CUSTOM_APP_BRANCH}" ]]; then
    git -C "${TARGET_DIR}" checkout -B "${CUSTOM_APP_BRANCH}" "origin/${CUSTOM_APP_BRANCH}"
  else
    git -C "${TARGET_DIR}" pull --ff-only
  fi
else
  rm -rf "${TARGET_DIR}"

  if [[ -n "${CUSTOM_APP_BRANCH}" ]]; then
    git clone --branch "${CUSTOM_APP_BRANCH}" "${CUSTOM_APP_REPO}" "${TARGET_DIR}"
  else
    git clone "${CUSTOM_APP_REPO}" "${TARGET_DIR}"
  fi
fi

git -C "${TARGET_DIR}" submodule update --init --recursive

cat <<EOF
Custom app checkout ready:
  ${TARGET_DIR}

Current revision:
  $(git -C "${TARGET_DIR}" rev-parse HEAD)
EOF
