#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
ACTION="${ACTION:-}"
TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID:-}"
RESUME_STATUS="${RESUME_STATUS:-}"
PARK_DECISION="${PARK_DECISION:-}"
PARK_REASON="${PARK_REASON:-}"
PARK_REVIEW_DATE="${PARK_REVIEW_DATE:-}"
WORK_NOTE="${WORK_NOTE:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_manage_delivery_parking_runner.rb"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

openproject_pod() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get pod \
    -l "app.kubernetes.io/component=web,app.kubernetes.io/name=openproject" \
    -o jsonpath='{.items[0].metadata.name}'
}

need_cmd "${KUBECTL%% *}"

if [[ -z "${ACTION}" ]]; then
  echo "ACTION is required, for example: make openproject-manage-delivery-parking ACTION=park TARGET_WORK_PACKAGE_ID=43 PARK_DECISION=retire PARK_REASON='No longer needed'" >&2
  exit 1
fi

if [[ -z "${TARGET_WORK_PACKAGE_ID}" ]]; then
  echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-parking ACTION=park TARGET_WORK_PACKAGE_ID=43 PARK_DECISION=retire PARK_REASON='No longer needed'" >&2
  exit 1
fi

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "Managing delivery parking for work item ${TARGET_WORK_PACKAGE_ID} in ${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}"

pod_name="$(openproject_pod)"
runner_remote="/tmp/openproject_manage_delivery_parking_runner.rb"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  ACTION="${ACTION}" \
  TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID}" \
  RESUME_STATUS="${RESUME_STATUS}" \
  PARK_DECISION="${PARK_DECISION}" \
  PARK_REASON="${PARK_REASON}" \
  PARK_REVIEW_DATE="${PARK_REVIEW_DATE}" \
  WORK_NOTE="${WORK_NOTE}" \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  sh -lc 'bundle exec rails runner "$1"' sh "${runner_remote}"
