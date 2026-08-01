#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly VALIDATION_PROFILE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly TEMP_ROOT="$(mktemp -d -t temporal-chart-validation-XXXXXX)"
trap 'rm -rf "${TEMP_ROOT}"' EXIT

export DEVINT_PROFILE_LIFECYCLE=build-admitted
export DEVINT_NAMESPACE=devint-temporal-validator
export DEVINT_OPERATOR=validator
export DEVINT_STATE_ROOT="${TEMP_ROOT}/state"

source "${SCRIPT_DIR}/common.sh"

need_cmd helm
need_cmd python3
need_cmd sha256sum
python3 "${SCRIPT_DIR}/test_generation_retirement.py"
render_runtime
ensure_chart

readonly RENDERED_CHART="${TEMP_ROOT}/temporal-rendered.yaml"
helm template "${RELEASE_NAME}" "${CHART_ARCHIVE}" \
  --namespace "${NAMESPACE}" \
  --values "${RENDERED_DIR}/temporal-values.yaml" \
  >"${RENDERED_CHART}"

python3 "${SCRIPT_DIR}/validate_source.py" \
  --profile-root "${VALIDATION_PROFILE_ROOT}" \
  --rendered-chart "${RENDERED_CHART}"
