#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
TARGET_EPIC_ID="${TARGET_EPIC_ID:-}"
DELIVERY_PLAN_FILE="${DELIVERY_PLAN_FILE:-}"
RECONCILE_MISSING="${RECONCILE_MISSING:-ignore}"
RECONCILE_DECISION="${RECONCILE_DECISION:-retire}"
RECONCILE_RETIREMENT_REASON="${RECONCILE_RETIREMENT_REASON:-superseded}"
RECONCILE_REASON="${RECONCILE_REASON:-}"
RECONCILE_REVIEW_DATE="${RECONCILE_REVIEW_DATE:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_apply_delivery_plan_runner.rb"

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
  echo "TARGET_EPIC_ID is required, for example: make openproject-apply-delivery-plan TARGET_EPIC_ID=38 DELIVERY_PLAN_FILE=/abs/path/delivery-plan.json" >&2
  exit 1
fi

if [[ -z "${DELIVERY_PLAN_FILE}" ]]; then
  echo "DELIVERY_PLAN_FILE is required, for example: make openproject-apply-delivery-plan TARGET_EPIC_ID=38 DELIVERY_PLAN_FILE=/abs/path/delivery-plan.json" >&2
  exit 1
fi

if [[ ! -f "${DELIVERY_PLAN_FILE}" ]]; then
  echo "Missing delivery plan file: ${DELIVERY_PLAN_FILE}" >&2
  exit 1
fi

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "Applying delivery plan ${DELIVERY_PLAN_FILE} to delivery epic ${TARGET_EPIC_ID}"

pod_name="$(openproject_pod)"
runner_remote="/tmp/openproject_apply_delivery_plan_runner.rb"
plan_remote="/tmp/openproject_delivery_plan.json"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${DELIVERY_PLAN_FILE}" "${pod_name}:${plan_remote}"

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" "${plan_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  TARGET_EPIC_ID="${TARGET_EPIC_ID}" \
  RECONCILE_MISSING="${RECONCILE_MISSING}" \
  RECONCILE_DECISION="${RECONCILE_DECISION}" \
  RECONCILE_RETIREMENT_REASON="${RECONCILE_RETIREMENT_REASON}" \
  RECONCILE_REASON="${RECONCILE_REASON}" \
  RECONCILE_REVIEW_DATE="${RECONCILE_REVIEW_DATE}" \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  sh -lc 'bundle exec rails runner "$1" "$2"' sh "${runner_remote}" "${plan_remote}"
