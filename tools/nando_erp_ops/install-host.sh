#!/usr/bin/env bash
# Install nando CLI on the ERP EC2 host (run as a user in the docker group).
set -euo pipefail

REPO="${NANDO_DOCKER_REPO:-/opt/nando_frappe_docker}"
VENV="${NANDO_OPS_VENV:-/opt/nando-erp-ops-venv}"

if [[ ! -d "${REPO}/tools/nando_erp_ops" ]]; then
  echo "Expected package at ${REPO}/tools/nando_erp_ops" >&2
  exit 1
fi

python3 -m venv "${VENV}"
"${VENV}/bin/pip" install -U pip
"${VENV}/bin/pip" install -e "${REPO}/tools/nando_erp_ops"

PROFILE="/etc/profile.d/nando-erp-ops.sh"
sudo tee "${PROFILE}" >/dev/null <<EOF
export NANDO_DOCKER_REPO=${REPO}
export NANDO_EXECUTOR=local
export PATH="${VENV}/bin:\$PATH"
EOF

echo "Installed. Open a new shell or: source ${PROFILE}"
echo "Try: nando-erp doctor --no-local"
