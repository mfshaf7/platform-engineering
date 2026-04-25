#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ADAPTER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_platform_admin_adapter.py"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_cmd "${KUBECTL%% *}"
need_cmd python3

if [[ ! -f "${ADAPTER_SCRIPT}" ]]; then
  echo "Missing adapter script: ${ADAPTER_SCRIPT}" >&2
  exit 1
fi

echo "Standardizing OpenProject delivery ART records in ${OPENPROJECT_NAMESPACE}/${OPENPROJECT_DEPLOYMENT}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}" \
TARGET_EPIC_ID="${TARGET_EPIC_ID:-}" \
python3 "${ADAPTER_SCRIPT}" --operation standardize-delivery-art
