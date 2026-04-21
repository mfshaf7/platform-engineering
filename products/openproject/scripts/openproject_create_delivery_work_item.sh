#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
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

if [[ -z "${BROKER_NAMESPACE}" ]]; then
  if [[ "${OPENPROJECT_NAMESPACE}" == "openproject" ]]; then
    BROKER_NAMESPACE="operator-orchestration-service"
  else
    BROKER_NAMESPACE="${OPENPROJECT_NAMESPACE}"
  fi
fi

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

echo "Creating delivery work item '${SUBJECT}' under parent ${PARENT_WORK_PACKAGE_ID}"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- \
  env \
    PARENT_WORK_PACKAGE_ID="${PARENT_WORK_PACKAGE_ID}" \
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
    BROKER_PORT="${BROKER_PORT}" \
    node --input-type=module - <<'NODE'
const brokerPort = process.env.BROKER_PORT || "8080";
const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-create-delivery-work-item";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";

const input = {
  parent_work_item_id: String(process.env.PARENT_WORK_PACKAGE_ID || "").trim(),
  subject: String(process.env.SUBJECT || "").trim(),
  type: String(process.env.TYPE || "").trim(),
};

const optionalFields = [
  ["status", "STATUS"],
  ["target_pi", "TARGET_PI"],
  ["assignee_login", "ASSIGNEE_LOGIN"],
  ["description", "DESCRIPTION"],
  ["start_date", "START_DATE"],
  ["due_date", "DUE_DATE"],
  ["estimated_work", "ESTIMATED_WORK"],
  ["remaining_work", "REMAINING_WORK"],
  ["percent_complete", "PERCENT_COMPLETE"],
  ["delivery_team", "DELIVERY_TEAM"],
  ["iteration", "ITERATION"],
  ["acceptance_criteria", "ACCEPTANCE_CRITERIA"],
  ["definition_of_ready", "DEFINITION_OF_READY"],
  ["definition_of_done", "DEFINITION_OF_DONE"],
  ["nfr_category", "NFR_CATEGORY"],
  ["pi_objective_type", "PI_OBJECTIVE_TYPE"],
  ["planned_business_value", "PLANNED_BUSINESS_VALUE"],
  ["actual_business_value", "ACTUAL_BUSINESS_VALUE"],
  ["roam_state", "ROAM_STATE"],
  ["risk_owner", "RISK_OWNER"],
  ["risk_review_date", "RISK_REVIEW_DATE"],
  ["risk_disposition", "RISK_DISPOSITION"],
  ["wsjf_user_business_value", "WSJF_USER_BUSINESS_VALUE"],
  ["wsjf_time_criticality", "WSJF_TIME_CRITICALITY"],
  ["wsjf_rr_oe", "WSJF_RR_OE"],
  ["wsjf_job_size", "WSJF_JOB_SIZE"],
];

for (const [fieldName, envName] of optionalFields) {
  const value = process.env[envName];
  if (typeof value === "string" && value.trim()) {
    input[fieldName] = value.trim();
  }
}

async function requestJson(url, { method = "GET", headers = {}, body } = {}) {
  const response = await fetch(url, { method, headers, body });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${method} ${url} failed: ${response.status} ${text}`);
  }
  return text ? JSON.parse(text) : null;
}

const brokerBase = `http://127.0.0.1:${brokerPort}`;
const ready = await requestJson(`${brokerBase}/readyz`);
if (!ready.ready) {
  throw new Error(`Broker is not ready: ${JSON.stringify(ready)}`);
}

const payload = await requestJson(`${brokerBase}/v1/delivery-work-items`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-correlation-id": `openproject-create-delivery-work-item-${Date.now()}`,
    "x-oos-caller-id": callerId,
    "x-oos-caller-secret": callerSecret,
  },
  body: JSON.stringify({ input }),
});

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
NODE

if [[ -n "${TARGET_PI}" ]]; then
  OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
  OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT}" \
  OPENPROJECT_DELIVERY_PI_NAMES="${TARGET_PI}" \
  "${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views.sh" >/dev/null
fi
