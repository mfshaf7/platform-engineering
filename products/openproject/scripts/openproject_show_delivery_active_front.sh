#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
TARGET_EPIC_ID="${TARGET_EPIC_ID:-}"
INCLUDE_DONE="${INCLUDE_DONE:-false}"
INCLUDE_PARKED="${INCLUDE_PARKED:-false}"

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

if [[ -z "${TARGET_EPIC_ID}" ]]; then
  echo "TARGET_EPIC_ID is required, for example: make openproject-show-delivery-active-front TARGET_EPIC_ID=38" >&2
  exit 1
fi

echo "Showing active delivery front for epic ${TARGET_EPIC_ID}"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- \
  env \
    TARGET_EPIC_ID="${TARGET_EPIC_ID}" \
    INCLUDE_DONE="${INCLUDE_DONE}" \
    INCLUDE_PARKED="${INCLUDE_PARKED}" \
    BROKER_PORT="${BROKER_PORT}" \
    node --input-type=module - <<'NODE'
const targetEpicId = process.env.TARGET_EPIC_ID?.trim();
const includeDone = (process.env.INCLUDE_DONE || "false").trim().toLowerCase() === "true";
const includeParked = (process.env.INCLUDE_PARKED || "false").trim().toLowerCase() === "true";
const brokerPort = process.env.BROKER_PORT || "8080";

if (!targetEpicId) {
  throw new Error("TARGET_EPIC_ID is required.");
}

const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-show-delivery-active-front";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";
const deliveryId = /^delivery-\d+$/.test(targetEpicId)
  ? targetEpicId
  : `delivery-${targetEpicId}`;

async function requestJson(url, { method = "GET", headers = {} } = {}) {
  const response = await fetch(url, { method, headers });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${method} ${url} failed: ${response.status} ${text}`);
  }
  return text ? JSON.parse(text) : null;
}

function pickTreeItems(node, items = []) {
  for (const child of node?.children || []) {
    items.push(child);
    pickTreeItems(child, items);
  }
  return items;
}

const brokerBase = `http://127.0.0.1:${brokerPort}`;
const ready = await requestJson(`${brokerBase}/readyz`);
if (!ready.ready) {
  throw new Error(`Broker is not ready: ${JSON.stringify(ready)}`);
}

const payload = await requestJson(
  `${brokerBase}/v1/delivery-initiatives/${deliveryId}/execution-summary?include_done=${includeDone}&include_parked=${includeParked}`,
  {
    headers: {
      "x-correlation-id": `openproject-show-delivery-active-front-${Date.now()}`,
      "x-oos-caller-id": callerId,
      "x-oos-caller-secret": callerSecret,
    },
  },
);

const summary = payload.execution_summary || {};
const epic = summary.epic || {};
const allItems = pickTreeItems(summary.execution_tree || {});
const activeItems = allItems.filter((item) =>
  ["in-progress", "ready", "blocked"].includes(String(item.status || "").trim().toLowerCase()),
);
const piObjectives = allItems.filter((item) => item.type === "PI Objective");
const risks = allItems.filter((item) => item.type === "Risk");
const topActiveItems = activeItems.slice(0, 12).map((item) => ({
  assignee: item.assignee ?? null,
  blocked: item.blocked ?? false,
  dependency_blocked: item.dependency_blocked ?? false,
  id: item.id,
  parent_id: item.parent_id ?? null,
  record_ref: item.record_ref,
  status: item.status,
  subject: item.subject,
  target_pi: item.target_pi ?? null,
  type: item.type,
}));

const result = {
  delivery_id: payload.delivery_id,
  delivery_record_ref: payload.delivery_record_ref,
  active_front: {
    epic,
    highlighted_items: topActiveItems,
    pi_objectives: piObjectives,
    risks,
    summary: summary.summary || {},
  },
  workflow_id: "delivery-active-front",
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
NODE
