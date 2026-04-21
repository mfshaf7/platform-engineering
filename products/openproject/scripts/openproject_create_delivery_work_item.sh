#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
PARENT_WORK_PACKAGE_ID="${PARENT_WORK_PACKAGE_ID:-}"
TYPE="${TYPE:-}"
SUBJECT="${SUBJECT:-}"
STATUS="${STATUS:-}"
TARGET_PI="${TARGET_PI:-}"
ASSIGNEE_LOGIN="${ASSIGNEE_LOGIN:-}"
DESCRIPTION="${DESCRIPTION:-}"
START_DATE="${START_DATE:-}"
DUE_DATE="${DUE_DATE:-}"
ESTIMATED_WORK="${ESTIMATED_WORK:-}"
REMAINING_WORK="${REMAINING_WORK:-}"
PERCENT_COMPLETE="${PERCENT_COMPLETE:-}"
DELIVERY_TEAM="${DELIVERY_TEAM:-}"
ITERATION="${ITERATION:-}"
ACCEPTANCE_CRITERIA="${ACCEPTANCE_CRITERIA:-}"
DEFINITION_OF_READY="${DEFINITION_OF_READY:-}"
DEFINITION_OF_DONE="${DEFINITION_OF_DONE:-}"
NFR_CATEGORY="${NFR_CATEGORY:-}"
PI_OBJECTIVE_TYPE="${PI_OBJECTIVE_TYPE:-}"
PLANNED_BUSINESS_VALUE="${PLANNED_BUSINESS_VALUE:-}"
ACTUAL_BUSINESS_VALUE="${ACTUAL_BUSINESS_VALUE:-}"
ROAM_STATE="${ROAM_STATE:-}"
RISK_OWNER="${RISK_OWNER:-}"
RISK_REVIEW_DATE="${RISK_REVIEW_DATE:-}"
RISK_DISPOSITION="${RISK_DISPOSITION:-}"
WSJF_USER_BUSINESS_VALUE="${WSJF_USER_BUSINESS_VALUE:-}"
WSJF_TIME_CRITICALITY="${WSJF_TIME_CRITICALITY:-}"
WSJF_RR_OE="${WSJF_RR_OE:-}"
WSJF_JOB_SIZE="${WSJF_JOB_SIZE:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_create_delivery_work_item_runner.rb"

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

if [[ -z "${PARENT_WORK_PACKAGE_ID}" ]]; then
  echo "PARENT_WORK_PACKAGE_ID is required, for example: make openproject-create-delivery-work-item PARENT_WORK_PACKAGE_ID=39 TYPE=Task SUBJECT='Inventory repo split'" >&2
  exit 1
fi

if [[ -z "${TYPE}" ]]; then
  echo "TYPE is required, for example: make openproject-create-delivery-work-item PARENT_WORK_PACKAGE_ID=39 TYPE=Task SUBJECT='Inventory repo split'" >&2
  exit 1
fi

if [[ -z "${SUBJECT}" ]]; then
  echo "SUBJECT is required, for example: make openproject-create-delivery-work-item PARENT_WORK_PACKAGE_ID=39 TYPE=Task SUBJECT='Inventory repo split'" >&2
  exit 1
fi

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "Creating delivery work item '${SUBJECT}' under parent ${PARENT_WORK_PACKAGE_ID} in ${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}"

pod_name="$(openproject_pod)"
runner_remote="/tmp/openproject_create_delivery_work_item_runner.rb"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  PARENT_WORK_PACKAGE_ID="${PARENT_WORK_PACKAGE_ID}" \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  TYPE="${TYPE}" \
  SUBJECT="${SUBJECT}" \
  STATUS="${STATUS}" \
  TARGET_PI="${TARGET_PI}" \
  ASSIGNEE_LOGIN="${ASSIGNEE_LOGIN}" \
  DESCRIPTION="${DESCRIPTION}" \
  START_DATE="${START_DATE}" \
  DUE_DATE="${DUE_DATE}" \
  ESTIMATED_WORK="${ESTIMATED_WORK}" \
  REMAINING_WORK="${REMAINING_WORK}" \
  PERCENT_COMPLETE="${PERCENT_COMPLETE}" \
  DELIVERY_TEAM="${DELIVERY_TEAM}" \
  ITERATION="${ITERATION}" \
  ACCEPTANCE_CRITERIA="${ACCEPTANCE_CRITERIA}" \
  DEFINITION_OF_READY="${DEFINITION_OF_READY}" \
  DEFINITION_OF_DONE="${DEFINITION_OF_DONE}" \
  NFR_CATEGORY="${NFR_CATEGORY}" \
  PI_OBJECTIVE_TYPE="${PI_OBJECTIVE_TYPE}" \
  PLANNED_BUSINESS_VALUE="${PLANNED_BUSINESS_VALUE}" \
  ACTUAL_BUSINESS_VALUE="${ACTUAL_BUSINESS_VALUE}" \
  ROAM_STATE="${ROAM_STATE}" \
  RISK_OWNER="${RISK_OWNER}" \
  RISK_REVIEW_DATE="${RISK_REVIEW_DATE}" \
  RISK_DISPOSITION="${RISK_DISPOSITION}" \
  WSJF_USER_BUSINESS_VALUE="${WSJF_USER_BUSINESS_VALUE}" \
  WSJF_TIME_CRITICALITY="${WSJF_TIME_CRITICALITY}" \
  WSJF_RR_OE="${WSJF_RR_OE}" \
  WSJF_JOB_SIZE="${WSJF_JOB_SIZE}" \
  sh -lc 'bundle exec rails runner "$1"' sh "${runner_remote}"

if [[ -n "${TARGET_PI}" ]]; then
  OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
  OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT}" \
  OPENPROJECT_DELIVERY_PI_NAMES="${TARGET_PI}" \
  "${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views.sh" >/dev/null
fi
