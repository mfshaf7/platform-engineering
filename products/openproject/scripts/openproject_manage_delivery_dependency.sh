#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
ACTION="${ACTION:-}"
TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID:-}"
DEPENDS_ON_WORK_PACKAGE_ID="${DEPENDS_ON_WORK_PACKAGE_ID:-}"
LAG="${LAG:-}"
CLEAR_LAG="${CLEAR_LAG:-false}"
DESCRIPTION="${DESCRIPTION:-}"
CLEAR_DESCRIPTION="${CLEAR_DESCRIPTION:-false}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_manage_delivery_dependency_runner.rb"

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
  echo "ACTION is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40" >&2
  exit 1
fi

if [[ -z "${TARGET_WORK_PACKAGE_ID}" ]]; then
  echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40" >&2
  exit 1
fi

if [[ -z "${DEPENDS_ON_WORK_PACKAGE_ID}" ]]; then
  echo "DEPENDS_ON_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40" >&2
  exit 1
fi

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "Managing delivery dependency for target ${TARGET_WORK_PACKAGE_ID} in ${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}"

pod_name="$(openproject_pod)"
runner_remote="/tmp/openproject_manage_delivery_dependency_runner.rb"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  ACTION="${ACTION}" \
  TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID}" \
  DEPENDS_ON_WORK_PACKAGE_ID="${DEPENDS_ON_WORK_PACKAGE_ID}" \
  LAG="${LAG}" \
  CLEAR_LAG="${CLEAR_LAG}" \
  DESCRIPTION="${DESCRIPTION}" \
  CLEAR_DESCRIPTION="${CLEAR_DESCRIPTION}" \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  sh -lc 'bundle exec rails runner "$1"' sh "${runner_remote}"
