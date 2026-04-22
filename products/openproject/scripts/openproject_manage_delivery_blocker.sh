#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID:-}"
ACTION="${ACTION:-}"
RESUME_STATUS="${RESUME_STATUS:-}"
BLOCKER_STATEMENT="${BLOCKER_STATEMENT:-}"
BLOCKER_IMPACT="${BLOCKER_IMPACT:-}"
BLOCKER_OWNER="${BLOCKER_OWNER:-}"
BLOCKER_DISCOVERED_ON="${BLOCKER_DISCOVERED_ON:-}"
BLOCKER_DECISION_PATH="${BLOCKER_DECISION_PATH:-}"
BLOCKER_JUSTIFICATION="${BLOCKER_JUSTIFICATION:-}"
BLOCKER_FOLLOW_UP_OWNER="${BLOCKER_FOLLOW_UP_OWNER:-}"
BLOCKER_REVIEW_DATE="${BLOCKER_REVIEW_DATE:-}"

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

if [[ -z "${TARGET_WORK_PACKAGE_ID}" ]]; then
  echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-blocker TARGET_WORK_PACKAGE_ID=40 ACTION=set ..." >&2
  exit 1
fi

if [[ -z "${ACTION}" ]]; then
  echo "ACTION is required and must be set or clear" >&2
  exit 1
fi

echo "Managing blocker state for delivery work item ${TARGET_WORK_PACKAGE_ID}"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- env \
  TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID}" \
  ACTION="${ACTION}" \
  RESUME_STATUS="${RESUME_STATUS}" \
  BLOCKER_STATEMENT="${BLOCKER_STATEMENT}" \
  BLOCKER_IMPACT="${BLOCKER_IMPACT}" \
  BLOCKER_OWNER="${BLOCKER_OWNER}" \
  BLOCKER_DISCOVERED_ON="${BLOCKER_DISCOVERED_ON}" \
  BLOCKER_DECISION_PATH="${BLOCKER_DECISION_PATH}" \
  BLOCKER_JUSTIFICATION="${BLOCKER_JUSTIFICATION}" \
  BLOCKER_FOLLOW_UP_OWNER="${BLOCKER_FOLLOW_UP_OWNER}" \
  BLOCKER_REVIEW_DATE="${BLOCKER_REVIEW_DATE}" \
  BROKER_PORT="${BROKER_PORT}" \
  node --input-type=module - <<'NODE'
const brokerPort = process.env.BROKER_PORT || "8080";
const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-manage-delivery-blocker";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";

const input = {
  action: String(process.env.ACTION || "").trim(),
};

const optionalFields = [
  ["resume_status", "RESUME_STATUS"],
  ["blocker_statement", "BLOCKER_STATEMENT"],
  ["blocker_impact", "BLOCKER_IMPACT"],
  ["blocker_owner", "BLOCKER_OWNER"],
  ["blocker_discovered_on", "BLOCKER_DISCOVERED_ON"],
  ["blocker_decision_path", "BLOCKER_DECISION_PATH"],
  ["blocker_justification", "BLOCKER_JUSTIFICATION"],
  ["blocker_follow_up_owner", "BLOCKER_FOLLOW_UP_OWNER"],
  ["blocker_review_date", "BLOCKER_REVIEW_DATE"],
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

const payload = await requestJson(
  `${brokerBase}/v1/delivery-work-items/work-item-${String(process.env.TARGET_WORK_PACKAGE_ID || "").trim()}/blocker`,
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-correlation-id": `openproject-manage-delivery-blocker-${Date.now()}`,
      "x-oos-caller-id": callerId,
      "x-oos-caller-secret": callerSecret,
    },
    body: JSON.stringify({ input }),
  },
);

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
NODE
