#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID:-}"
COMPLETION_SUMMARY="${COMPLETION_SUMMARY:-}"
COMPLETION_SUMMARY_FILE="${COMPLETION_SUMMARY_FILE:-}"
CHANGED_SURFACES="${CHANGED_SURFACES:-}"
CHANGED_SURFACES_FILE="${CHANGED_SURFACES_FILE:-}"
TEST_RESULT_EVIDENCE="${TEST_RESULT_EVIDENCE:-}"
TEST_RESULT_EVIDENCE_FILE="${TEST_RESULT_EVIDENCE_FILE:-}"
TEST_RESULT_ARTIFACT_FILE="${TEST_RESULT_ARTIFACT_FILE:-}"
TEST_RESULT_ARTIFACT_DESCRIPTION="${TEST_RESULT_ARTIFACT_DESCRIPTION:-}"
VALIDATION_EVIDENCE="${VALIDATION_EVIDENCE:-}"
VALIDATION_EVIDENCE_FILE="${VALIDATION_EVIDENCE_FILE:-}"
COMPLETION_NOTE="${COMPLETION_NOTE:-}"
COMPLETION_NOTE_FILE="${COMPLETION_NOTE_FILE:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_complete_delivery_work_item_runner.rb"
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

read_value() {
  local value="$1"
  local file_path="$2"
  local label="$3"

  if [[ -n "${value}" && -n "${file_path}" ]]; then
    echo "${label} and ${label}_FILE cannot be used together" >&2
    exit 1
  fi

  if [[ -n "${file_path}" ]]; then
    if [[ ! -f "${file_path}" ]]; then
      echo "Missing ${label}_FILE: ${file_path}" >&2
      exit 1
    fi
    cat "${file_path}"
    return
  fi

  printf '%s' "${value}"
}

need_cmd "${KUBECTL%% *}"

if [[ -z "${TARGET_WORK_PACKAGE_ID}" ]]; then
  echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-complete-delivery-work-item TARGET_WORK_PACKAGE_ID=55 COMPLETION_SUMMARY='Implemented the broker read surface' CHANGED_SURFACES='- src/app.js' TEST_RESULT_EVIDENCE='- PASS: execution summary contract test' VALIDATION_EVIDENCE='- npm test'" >&2
  exit 1
fi

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "${SUPPORT_SCRIPT}" ]]; then
  echo "Missing support script: ${SUPPORT_SCRIPT}" >&2
  exit 1
fi

COMPLETION_SUMMARY="$(read_value "${COMPLETION_SUMMARY}" "${COMPLETION_SUMMARY_FILE}" "COMPLETION_SUMMARY")"
CHANGED_SURFACES="$(read_value "${CHANGED_SURFACES}" "${CHANGED_SURFACES_FILE}" "CHANGED_SURFACES")"
TEST_RESULT_EVIDENCE="$(read_value "${TEST_RESULT_EVIDENCE}" "${TEST_RESULT_EVIDENCE_FILE}" "TEST_RESULT_EVIDENCE")"
VALIDATION_EVIDENCE="$(read_value "${VALIDATION_EVIDENCE}" "${VALIDATION_EVIDENCE_FILE}" "VALIDATION_EVIDENCE")"
COMPLETION_NOTE="$(read_value "${COMPLETION_NOTE}" "${COMPLETION_NOTE_FILE}" "COMPLETION_NOTE")"

if [[ -z "${COMPLETION_SUMMARY}" ]]; then
  echo "COMPLETION_SUMMARY or COMPLETION_SUMMARY_FILE is required" >&2
  exit 1
fi

if [[ -z "${CHANGED_SURFACES}" ]]; then
  echo "CHANGED_SURFACES or CHANGED_SURFACES_FILE is required" >&2
  exit 1
fi

if [[ -z "${TEST_RESULT_EVIDENCE}" ]]; then
  echo "TEST_RESULT_EVIDENCE or TEST_RESULT_EVIDENCE_FILE is required" >&2
  exit 1
fi

if [[ -z "${VALIDATION_EVIDENCE}" ]]; then
  echo "VALIDATION_EVIDENCE or VALIDATION_EVIDENCE_FILE is required" >&2
  exit 1
fi

if [[ -n "${TEST_RESULT_ARTIFACT_FILE}" && ! -f "${TEST_RESULT_ARTIFACT_FILE}" ]]; then
  echo "Missing TEST_RESULT_ARTIFACT_FILE: ${TEST_RESULT_ARTIFACT_FILE}" >&2
  exit 1
fi

echo "Completing delivery work item ${TARGET_WORK_PACKAGE_ID} in ${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}"

pod_name="$(openproject_pod)"
runner_remote="/tmp/openproject_complete_delivery_work_item_runner.rb"
support_remote="/tmp/openproject_delivery_art_custom_field_support.rb"
artifact_remote=""
artifact_name=""

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${RUNNER_SCRIPT}" "${pod_name}:${runner_remote}"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${SUPPORT_SCRIPT}" "${pod_name}:${support_remote}"

if [[ -n "${TEST_RESULT_ARTIFACT_FILE}" ]]; then
  artifact_name="$(basename "${TEST_RESULT_ARTIFACT_FILE}")"
  artifact_remote="/tmp/${artifact_name}"
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" cp "${TEST_RESULT_ARTIFACT_FILE}" "${pod_name}:${artifact_remote}"
fi

cleanup() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${runner_remote}" "${support_remote}" >/dev/null 2>&1 || true
  if [[ -n "${artifact_remote}" ]]; then
    kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- rm -f "${artifact_remote}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "${pod_name}" -- env \
  TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID}" \
  OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
  COMPLETION_SUMMARY="${COMPLETION_SUMMARY}" \
  CHANGED_SURFACES="${CHANGED_SURFACES}" \
  TEST_RESULT_EVIDENCE="${TEST_RESULT_EVIDENCE}" \
  TEST_RESULT_ARTIFACT_PATH="${artifact_remote}" \
  TEST_RESULT_ARTIFACT_NAME="${artifact_name}" \
  TEST_RESULT_ARTIFACT_DESCRIPTION="${TEST_RESULT_ARTIFACT_DESCRIPTION}" \
  VALIDATION_EVIDENCE="${VALIDATION_EVIDENCE}" \
  COMPLETION_NOTE="${COMPLETION_NOTE}" \
  sh -lc 'bundle exec rails runner "$1"' sh "${runner_remote}"
