#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID:-}"
NEW_PARENT_WORK_PACKAGE_ID="${NEW_PARENT_WORK_PACKAGE_ID:-}"
WORK_NOTE="${WORK_NOTE:-}"

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
  echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-move-delivery-work-item TARGET_WORK_PACKAGE_ID=40 NEW_PARENT_WORK_PACKAGE_ID=43" >&2
  exit 1
fi

if [[ -z "${NEW_PARENT_WORK_PACKAGE_ID}" ]]; then
  echo "NEW_PARENT_WORK_PACKAGE_ID is required, for example: make openproject-move-delivery-work-item TARGET_WORK_PACKAGE_ID=40 NEW_PARENT_WORK_PACKAGE_ID=43" >&2
  exit 1
fi

echo "Moving delivery work item ${TARGET_WORK_PACKAGE_ID} under new parent ${NEW_PARENT_WORK_PACKAGE_ID}"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- env \
  TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID}" \
  NEW_PARENT_WORK_PACKAGE_ID="${NEW_PARENT_WORK_PACKAGE_ID}" \
  WORK_NOTE="${WORK_NOTE}" \
  BROKER_PORT="${BROKER_PORT}" \
  node --input-type=module - <<'NODE'
const brokerPort = process.env.BROKER_PORT || "8080";
const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-move-delivery-work-item";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";

const workItemId = String(process.env.TARGET_WORK_PACKAGE_ID || "").trim();
const newParentWorkItemId = String(process.env.NEW_PARENT_WORK_PACKAGE_ID || "").trim();
const workNote = String(process.env.WORK_NOTE || "").trim();

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

const input = {
  new_parent_work_item_id: newParentWorkItemId,
};

if (workNote) {
  input.work_note = workNote;
}

const payload = await requestJson(
  `${brokerBase}/v1/delivery-work-items/work-item-${workItemId}/move`,
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-correlation-id": `openproject-move-delivery-work-item-${Date.now()}`,
      "x-oos-caller-id": callerId,
      "x-oos-caller-secret": callerSecret,
    },
    body: JSON.stringify({ input }),
  },
);

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
NODE
