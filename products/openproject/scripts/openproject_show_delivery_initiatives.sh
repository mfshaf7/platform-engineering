#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
INCLUDE_DONE="${INCLUDE_DONE:-true}"
INCLUDE_INACTIVE="${INCLUDE_INACTIVE:-false}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_show_delivery_initiatives_runner.rb"
SUPPORT_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_delivery_art_custom_field_support.rb"

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

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "${SUPPORT_SCRIPT}" ]]; then
  echo "Missing support script: ${SUPPORT_SCRIPT}" >&2
  exit 1
fi

echo "Showing delivery initiatives in ${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}"

pod_name="$(openproject_pod)"
runner_basename="$(basename "${RUNNER_SCRIPT}" .rb)"
runner_remote="/tmp/${runner_basename}-$$.rb"
support_remote="/tmp/openproject_delivery_art_custom_field_support.rb"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${SUPPORT_SCRIPT}" "${pod_name}:${support_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" "${support_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  INCLUDE_DONE="${INCLUDE_DONE}" \
  INCLUDE_INACTIVE="${INCLUDE_INACTIVE}" \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  sh -lc 'bundle exec rails runner "$1"' sh "${runner_remote}"
