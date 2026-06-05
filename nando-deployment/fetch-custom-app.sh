#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
APPS_ROOT="${SCRIPT_DIR}/custom-apps"
GITHUB_SECRETS_FILE="${SCRIPT_DIR}/github.env"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

INCLUDE_CUSTOM_APP="${INCLUDE_CUSTOM_APP:-yes}"
if ! include_custom_app_enabled "${INCLUDE_CUSTOM_APP}"; then
  echo "INCLUDE_CUSTOM_APP=${INCLUDE_CUSTOM_APP} — skipping custom app fetch (${ENV_FILE})."
  exit 0
fi

load_github_token "${GITHUB_SECRETS_FILE}"

git_with_github_auth() {
  GIT_TERMINAL_PROMPT=0 git -c credential.helper= "$@"
}

list_remote_branches() {
  local auth_repo="$1"
  git_with_github_auth ls-remote --heads "${auth_repo}" | awk -F/ '{print $NF}'
}

resolve_remote_branch() {
  local auth_repo="$1"
  local branch="$2"
  local env_prefix="$3"

  if [[ -n "${branch}" ]]; then
    if git_with_github_auth ls-remote --exit-code --heads "${auth_repo}" "refs/heads/${branch}" >/dev/null 2>&1; then
      echo "${branch}"
      return 0
    fi

    cat >&2 <<EOF
Branch '${branch}' not found for ${env_prefix}.

Remote branches:
$(list_remote_branches "${auth_repo}" | sed 's/^/  /')

Update ${env_prefix}_BRANCH in ${ENV_FILE}.
EOF
    return 1
  fi

  local default_branch
  default_branch="$(
    git_with_github_auth ls-remote --symref "${auth_repo}" HEAD \
      | awk '/^ref:/ { sub(/^refs\/heads\//, "", $2); print $2; exit }'
  )"
  if [[ -z "${default_branch}" ]]; then
    echo "Could not determine default branch for ${auth_repo}" >&2
    return 1
  fi
  echo "${default_branch}"
}

mkdir -p "${APPS_ROOT}"

fetch_one_app() {
  local key="$1"
  local repo branch target_dir current_remote canonical_repo auth_repo env_prefix

  if ! repo="$(get_custom_app_repo "${key}")"; then
    local prefix
    prefix="$(custom_app_env_prefix "${key}")"
    echo "No repo configured for app key '${key}' (set ${prefix}_REPO in ${ENV_FILE})" >&2
    return 1
  fi

  env_prefix="$(custom_app_env_prefix "${key}")"
  target_dir="${APPS_ROOT}/${key}"
  canonical_repo="$(github_repo_canonical_url "${repo}")"
  auth_repo="$(github_repo_auth_url "${repo}")"
  branch="$(resolve_remote_branch "${auth_repo}" "$(get_custom_app_branch "${key}")" "${env_prefix}")"

  if [[ -d "${target_dir}/.git" ]]; then
    current_remote="$(git -C "${target_dir}" remote get-url origin)"
    if ! repos_match "${current_remote}" "${repo}"; then
      cat >&2 <<EOF
Existing checkout for ${key} uses a different remote:
  ${current_remote}

Expected:
  ${canonical_repo}

Remove ${target_dir} if you want to replace it.
EOF
      return 1
    fi

    if [[ "${current_remote}" != "${canonical_repo}" ]]; then
      git -C "${target_dir}" remote set-url origin "${canonical_repo}"
    fi

    git_with_github_auth -C "${target_dir}" fetch --tags --prune "${auth_repo}" \
      "+refs/heads/*:refs/remotes/origin/*" "+refs/tags/*:refs/tags/*"

    if [[ -n "${branch}" ]]; then
      git -C "${target_dir}" checkout -B "${branch}" "origin/${branch}"
    else
      current_branch="$(git -C "${target_dir}" branch --show-current)"
      git_with_github_auth -C "${target_dir}" pull --ff-only "${auth_repo}" "${current_branch}"
    fi
  else
    rm -rf "${target_dir}"

    if [[ -n "${branch}" ]]; then
      git_with_github_auth clone --branch "${branch}" "${auth_repo}" "${target_dir}"
    else
      git_with_github_auth clone "${auth_repo}" "${target_dir}"
    fi

    git -C "${target_dir}" remote set-url origin "${canonical_repo}"
  fi

  git_with_github_auth -C "${target_dir}" \
    -c "http.extraHeader=Authorization: Bearer ${GITHUB_TOKEN}" \
    submodule update --init --recursive

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
