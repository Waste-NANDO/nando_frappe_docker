#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
APPS_ROOT="${SCRIPT_DIR}/custom-apps"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

INCLUDE_CUSTOM_APP="${INCLUDE_CUSTOM_APP:-yes}"
if ! include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
  echo "INCLUDE_CUSTOM_APP=${INCLUDE_CUSTOM_APP} — skipping custom app fetch (${ENV_FILE})."
  exit 0
fi

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

mkdir -p "${APPS_ROOT}"

fetch_one_app() {
  local key="$1"
  local repo branch target_dir current_remote

  if ! repo="$(get_custom_app_repo "${key}")"; then
    local prefix
    prefix="$(custom_app_env_prefix "${key}")"
    echo "No repo configured for app key '${key}' (set ${prefix}_REPO or legacy CUSTOM_APP_REPO)" >&2
    return 1
  fi

  branch="$(get_custom_app_branch "${key}")"
  target_dir="${APPS_ROOT}/${key}"

  if [[ -d "${target_dir}/.git" ]]; then
    current_remote="$(git -C "${target_dir}" remote get-url origin)"
    if [[ "${current_remote}" != "${repo}" ]]; then
      cat >&2 <<EOF
Existing checkout for ${key} uses a different remote:
  ${current_remote}

Expected:
  ${repo}

Remove ${target_dir} if you want to replace it.
EOF
      return 1
    fi

    git -C "${target_dir}" fetch --tags --prune origin

    if [[ -n "${branch}" ]]; then
      git -C "${target_dir}" checkout -B "${branch}" "origin/${branch}"
    else
      git -C "${target_dir}" pull --ff-only
    fi
  else
    rm -rf "${target_dir}"

    if [[ -n "${branch}" ]]; then
      git clone --branch "${branch}" "${repo}" "${target_dir}"
    else
      git clone "${repo}" "${target_dir}"
    fi
  fi

  git -C "${target_dir}" submodule update --init --recursive

  cat <<EOF
Custom app checkout ready:
  ${key} → ${target_dir}
  revision: $(git -C "${target_dir}" rev-parse --short HEAD)
EOF
}

read -r -a app_keys <<< "$(resolve_custom_app_keys)"
if [[ "${#app_keys[@]}" -eq 0 ]]; then
  echo "No custom app keys configured (set CUSTOM_APP_KEYS in ${ENV_FILE})" >&2
  exit 1
fi

for key in "${app_keys[@]}"; do
  key="$(echo "${key}" | xargs)"
  [[ -z "${key}" ]] && continue
  fetch_one_app "${key}"
done

cat <<EOF

All custom apps fetched under:
  ${APPS_ROOT}
EOF
