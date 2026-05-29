#!/usr/bin/env bash
# shellcheck disable=SC2034
# Resolve deployment env file: explicit arg > erpnext-dev.env > erpnext.env
resolve_env_file() {
  local script_dir="$1"
  local explicit="${2:-}"

  if [[ -n "${explicit}" ]]; then
    if [[ ! -f "${explicit}" ]]; then
      echo "Env file not found: ${explicit}" >&2
      return 1
    fi
    echo "${explicit}"
    return 0
  fi

  if [[ -f "${script_dir}/erpnext-dev.env" ]]; then
    echo "${script_dir}/erpnext-dev.env"
    return 0
  fi

  if [[ -f "${script_dir}/erpnext.env" ]]; then
    echo "Note: using legacy erpnext.env; prefer erpnext-dev.env for dev." >&2
    echo "${script_dir}/erpnext.env"
    return 0
  fi

  echo "No env file found. Pass a path or add erpnext-dev.env / erpnext.env under ${script_dir}" >&2
  return 1
}

include_custom_app_enabled() {
  local value
  value="$(echo "${1:-yes}" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    yes | true | 1) return 0 ;;
    *) return 1 ;;
  esac
}
