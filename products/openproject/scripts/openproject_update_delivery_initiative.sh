#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
TARGET_EPIC_ID="${TARGET_EPIC_ID:-}"
PM2_PHASE="${PM2_PHASE:-}"
TARGET_PI="${TARGET_PI:-}"
SPONSOR="${SPONSOR:-}"
BUSINESS_OBJECTIVE="${BUSINESS_OBJECTIVE:-}"
SUCCESS_CRITERIA="${SUCCESS_CRITERIA:-}"
STATUS="${STATUS:-}"
DESCRIPTION="${DESCRIPTION:-}"
SYSTEM_DEMO_EVIDENCE="${SYSTEM_DEMO_EVIDENCE:-}"
INSPECT_AND_ADAPT_ACTIONS="${INSPECT_AND_ADAPT_ACTIONS:-}"
NFR_CATEGORY="${NFR_CATEGORY:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_update_delivery_initiative_runner.rb"

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

if [[ -z "${TARGET_EPIC_ID}" ]]; then
  echo "TARGET_EPIC_ID is required, for example: make openproject-update-delivery-initiative TARGET_EPIC_ID=38 PM2_PHASE=Planning TARGET_PI=PI-2026-02 SPONSOR=mfshaf7 STATUS=in-progress" >&2
  exit 1
fi

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "Updating delivery initiative ${TARGET_EPIC_ID} in ${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}"

pod_name="$(openproject_pod)"
runner_remote="/tmp/openproject_update_delivery_initiative_runner.rb"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  TARGET_EPIC_ID="${TARGET_EPIC_ID}" \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  PM2_PHASE="${PM2_PHASE}" \
  TARGET_PI="${TARGET_PI}" \
  SPONSOR="${SPONSOR}" \
  BUSINESS_OBJECTIVE="${BUSINESS_OBJECTIVE}" \
  SUCCESS_CRITERIA="${SUCCESS_CRITERIA}" \
  SYSTEM_DEMO_EVIDENCE="${SYSTEM_DEMO_EVIDENCE}" \
  INSPECT_AND_ADAPT_ACTIONS="${INSPECT_AND_ADAPT_ACTIONS}" \
  NFR_CATEGORY="${NFR_CATEGORY}" \
  STATUS="${STATUS}" \
  DESCRIPTION="${DESCRIPTION}" \
  sh -lc 'bundle exec rails runner "$1"' sh "${runner_remote}"

if [[ -n "${TARGET_PI}" ]]; then
  OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
  OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT}" \
  OPENPROJECT_DELIVERY_PI_NAMES="${TARGET_PI}" \
  "${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views.sh" >/dev/null
fi
