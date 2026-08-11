#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CHECKER="${REPO_ROOT}/products/openproject/scripts/openproject_check_delivery_art_quality.py"

if [[ ! -f "${CHECKER}" ]]; then
  echo "Missing quality projection adapter: ${CHECKER}" >&2
  exit 1
fi

python3 "${CHECKER}"
