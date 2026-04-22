#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
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

if [[ -z "${TARGET_EPIC_ID}" ]]; then
  echo "TARGET_EPIC_ID is required, for example: make openproject-update-delivery-initiative TARGET_EPIC_ID=38 PM2_PHASE=Planning TARGET_PI=PI-2026-02 SPONSOR=mfshaf7 STATUS=in-progress" >&2
  exit 1
fi

if [[ -z "${BROKER_NAMESPACE}" ]]; then
  if [[ "${OPENPROJECT_NAMESPACE}" == "openproject" ]]; then
    BROKER_NAMESPACE="operator-orchestration-service"
  else
    BROKER_NAMESPACE="${OPENPROJECT_NAMESPACE}"
  fi
fi

echo "Updating delivery initiative ${TARGET_EPIC_ID} through the broker-owned governance route"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- env \
  TARGET_EPIC_ID="${TARGET_EPIC_ID}" \
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
  BROKER_PORT="${BROKER_PORT}" \
  node --input-type=module - <<'NODE'
const brokerPort = process.env.BROKER_PORT || "8080";
const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-update-delivery-initiative";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";
const deliveryId = `delivery-${String(process.env.TARGET_EPIC_ID || "").trim()}`;

const input = {};
for (const [envName, fieldName] of [
  ["PM2_PHASE", "pm2_phase"],
  ["TARGET_PI", "target_pi"],
  ["SPONSOR", "sponsor"],
  ["BUSINESS_OBJECTIVE", "business_objective"],
  ["SUCCESS_CRITERIA", "success_criteria"],
  ["SYSTEM_DEMO_EVIDENCE", "system_demo_evidence"],
  ["INSPECT_AND_ADAPT_ACTIONS", "inspect_and_adapt_actions"],
  ["NFR_CATEGORY", "nfr_category"],
  ["STATUS", "status"],
  ["DESCRIPTION", "description"],
]) {
  const value = process.env[envName];
  if (typeof value === "string" && value.trim()) {
    input[fieldName] = value.trim();
  }
}

if (Object.keys(input).length === 0) {
  throw new Error("At least one governance field or status must be supplied");
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

const payload = await requestJson(`${brokerBase}/v1/delivery-initiatives/${deliveryId}/governance`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-correlation-id": `openproject-update-delivery-initiative-${Date.now()}`,
    "x-oos-caller-id": callerId,
    "x-oos-caller-secret": callerSecret,
  },
  body: JSON.stringify({ input }),
});

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
NODE

if [[ -n "${TARGET_PI}" ]]; then
  OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
  OPENPROJECT_DELIVERY_PI_NAMES="${TARGET_PI}" \
  "${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views.sh" >/dev/null
fi
