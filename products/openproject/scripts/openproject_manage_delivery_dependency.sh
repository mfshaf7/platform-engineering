#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
ACTION="${ACTION:-}"
TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID:-}"
DEPENDS_ON_WORK_PACKAGE_ID="${DEPENDS_ON_WORK_PACKAGE_ID:-}"
LAG="${LAG:-}"
CLEAR_LAG="${CLEAR_LAG:-false}"
DESCRIPTION="${DESCRIPTION:-}"
CLEAR_DESCRIPTION="${CLEAR_DESCRIPTION:-false}"

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

if [[ -z "${ACTION}" ]]; then
  echo "ACTION is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40" >&2
  exit 1
fi

if [[ -z "${TARGET_WORK_PACKAGE_ID}" ]]; then
  echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40" >&2
  exit 1
fi

if [[ -z "${DEPENDS_ON_WORK_PACKAGE_ID}" ]]; then
  echo "DEPENDS_ON_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40" >&2
  exit 1
fi

echo "Managing delivery dependency for target ${TARGET_WORK_PACKAGE_ID}"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- env \
  ACTION="${ACTION}" \
  TARGET_WORK_PACKAGE_ID="${TARGET_WORK_PACKAGE_ID}" \
  DEPENDS_ON_WORK_PACKAGE_ID="${DEPENDS_ON_WORK_PACKAGE_ID}" \
  LAG="${LAG}" \
  CLEAR_LAG="${CLEAR_LAG}" \
  DESCRIPTION="${DESCRIPTION}" \
  CLEAR_DESCRIPTION="${CLEAR_DESCRIPTION}" \
  BROKER_PORT="${BROKER_PORT}" \
  node --input-type=module - <<'NODE'
const brokerPort = process.env.BROKER_PORT || "8080";
const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-manage-delivery-dependency";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";

const input = {
  action: String(process.env.ACTION || "").trim(),
  depends_on_work_item_id: `work-item-${String(process.env.DEPENDS_ON_WORK_PACKAGE_ID || "").trim()}`,
};

const lagValue = String(process.env.LAG || "").trim();
if (lagValue) {
  input.lag = Number.parseInt(lagValue, 10);
}

if (String(process.env.CLEAR_LAG || "").trim().toLowerCase() === "true") {
  input.clear_lag = true;
}

const descriptionValue = String(process.env.DESCRIPTION || "").trim();
if (descriptionValue) {
  input.description = descriptionValue;
}

if (String(process.env.CLEAR_DESCRIPTION || "").trim().toLowerCase() === "true") {
  input.clear_description = true;
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
  `${brokerBase}/v1/delivery-work-items/work-item-${String(process.env.TARGET_WORK_PACKAGE_ID || "").trim()}/dependency`,
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-correlation-id": `openproject-manage-delivery-dependency-${Date.now()}`,
      "x-oos-caller-id": callerId,
      "x-oos-caller-secret": callerSecret,
    },
    body: JSON.stringify({ input }),
  },
);

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
NODE
