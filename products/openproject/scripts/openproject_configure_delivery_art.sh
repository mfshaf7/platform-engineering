#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_configure_delivery_art_runner.rb"
HOME_SUPPORT_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_delivery_art_home_support.rb"
TAXONOMY_SUPPORT_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_delivery_art_taxonomy_support.rb"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

need_cmd "${KUBECTL%% *}"

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "${HOME_SUPPORT_SCRIPT}" ]]; then
  echo "Missing support script: ${HOME_SUPPORT_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "${TAXONOMY_SUPPORT_SCRIPT}" ]]; then
  echo "Missing support script: ${TAXONOMY_SUPPORT_SCRIPT}" >&2
  exit 1
fi

echo "Configuring OpenProject delivery ART model in ${OPENPROJECT_NAMESPACE}/${OPENPROJECT_DEPLOYMENT}"

pod_name="$(${KUBECTL} -n "${OPENPROJECT_NAMESPACE}" get pod -l "app.kubernetes.io/component=web,app.kubernetes.io/name=openproject" -o jsonpath='{.items[0].metadata.name}')"
runner_remote="/tmp/openproject_configure_delivery_art_runner.rb"
support_remote="/tmp/openproject_delivery_art_home_support.rb"
taxonomy_support_remote="/tmp/openproject_delivery_art_taxonomy_support.rb"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${HOME_SUPPORT_SCRIPT}" "${pod_name}:${support_remote}"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${TAXONOMY_SUPPORT_SCRIPT}" "${pod_name}:${taxonomy_support_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" "${support_remote}" "${taxonomy_support_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- sh -lc 'bundle exec rails runner "$1"' sh "${runner_remote}"

OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT}" \
OPENPROJECT_DELIVERY_PI_NAMES="${OPENPROJECT_DELIVERY_PI_NAMES:-}" \
"${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views.sh"
