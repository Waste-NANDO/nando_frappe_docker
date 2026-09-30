#!/usr/bin/env bash
# Weekly Quality data refresh from prod GCS backup.
# Install on the ERP host (after cutover), e.g.:
#   15 3 * * 0 /opt/nando_frappe_docker/nando-deployment/cron/quality-refresh.sh >> /var/log/nando-quality-refresh.log 2>&1
set -euo pipefail

export NANDO_EXECUTOR=local
export NANDO_DOCKER_REPO="${NANDO_DOCKER_REPO:-/opt/nando_frappe_docker}"
export PATH="/opt/nando-erp-ops-venv/bin:${PATH}"

cd "${NANDO_DOCKER_REPO}"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] quality refresh start"
nando-erp refresh --target quality --skip-if-drift
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] quality refresh done"
