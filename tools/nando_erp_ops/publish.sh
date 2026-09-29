#!/usr/bin/env bash
# Publish nando-erp-ops to GCP Artifact Registry.
# Requires: python -m build, twine, gcloud auth application-default login (or key).
#
# Usage:
#   ./publish.sh [PROJECT] [REPO] [REGION]
# Defaults: PROJECT from gcloud config, REPO=python-packages, REGION=europe-west1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-$(gcloud config get-value project 2>/dev/null)}"
REPO="${2:-python-packages}"
REGION="${3:-europe-west1}"

if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "Pass GCP project id as first arg" >&2
  exit 1
fi

cd "${SCRIPT_DIR}"
python3 -m pip install -q build twine keyrings.google-artifactregistry-auth
rm -rf dist build *.egg-info
python3 -m build

URL="https://${REGION}-python.pkg.dev/${PROJECT}/${REPO}/"
echo "Uploading to ${URL}"
python3 -m twine upload --repository-url "${URL}" dist/*
echo "Install with:"
echo "  pip install nando-erp-ops --index-url ${URL}simple/"
