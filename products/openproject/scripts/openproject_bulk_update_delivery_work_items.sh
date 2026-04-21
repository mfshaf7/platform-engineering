#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
DELIVERY_WORK_ITEM_UPDATE_FILE="${DELIVERY_WORK_ITEM_UPDATE_FILE:-}"
OPENPROJECT_DELIVERY_PI_NAMES="${OPENPROJECT_DELIVERY_PI_NAMES:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_bulk_update_delivery_work_items_runner.rb"

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

if [[ -z "${DELIVERY_WORK_ITEM_UPDATE_FILE}" ]]; then
  echo "DELIVERY_WORK_ITEM_UPDATE_FILE is required, for example: make openproject-bulk-update-delivery-work-items DELIVERY_WORK_ITEM_UPDATE_FILE=/abs/path/work-item-updates.json" >&2
  exit 1
fi

if [[ ! -f "${DELIVERY_WORK_ITEM_UPDATE_FILE}" ]]; then
  echo "Missing bulk update file: ${DELIVERY_WORK_ITEM_UPDATE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "Applying bulk delivery work-item updates from ${DELIVERY_WORK_ITEM_UPDATE_FILE}"

pod_name="$(openproject_pod)"
runner_remote="/tmp/openproject_bulk_update_delivery_work_items_runner.rb"
update_remote="/tmp/openproject_bulk_delivery_work_item_updates.json"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${DELIVERY_WORK_ITEM_UPDATE_FILE}" "${pod_name}:${update_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" "${update_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  sh -lc 'bundle exec rails runner "$1" "$2"' sh "${runner_remote}" "${update_remote}"

OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT}" \
OPENPROJECT_DELIVERY_PI_NAMES="${OPENPROJECT_DELIVERY_PI_NAMES}" \
"${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views.sh" >/dev/null
