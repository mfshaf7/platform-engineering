#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
TARGET_EPIC_ID="${TARGET_EPIC_ID:-}"
DELIVERY_PLAN_FILE="${DELIVERY_PLAN_FILE:-}"
RECONCILE_MISSING="${RECONCILE_MISSING:-ignore}"
RECONCILE_DECISION="${RECONCILE_DECISION:-retire}"
RECONCILE_RETIREMENT_REASON="${RECONCILE_RETIREMENT_REASON:-superseded}"
RECONCILE_REASON="${RECONCILE_REASON:-}"
RECONCILE_REVIEW_DATE="${RECONCILE_REVIEW_DATE:-}"
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

if [[ -z "${BROKER_NAMESPACE}" ]]; then
  if [[ "${OPENPROJECT_NAMESPACE}" == "openproject" ]]; then
    BROKER_NAMESPACE="operator-orchestration-service"
  else
    BROKER_NAMESPACE="${OPENPROJECT_NAMESPACE}"
  fi
fi

SYNC_PI_NAMES="$(
  node --input-type=module -e '
    import fs from "node:fs";
    const planPath = process.argv[1];
    const plan = JSON.parse(fs.readFileSync(planPath, "utf8"));
    const names = new Set();
    const collect = (item) => {
      const targetPi = typeof item?.target_pi === "string" ? item.target_pi.trim() : "";
      if (targetPi) names.add(targetPi);
      for (const child of Array.isArray(item?.children) ? item.children : []) {
        collect(child);
      }
    };
    const epicTargetPi = typeof plan?.epic_updates?.target_pi === "string" ? plan.epic_updates.target_pi.trim() : "";
    if (epicTargetPi) names.add(epicTargetPi);
    for (const item of Array.isArray(plan?.items) ? plan.items : []) {
      collect(item);
    }
    process.stdout.write(Array.from(names).join(","));
  ' "${DELIVERY_PLAN_FILE}"
)"

echo "Applying delivery plan ${DELIVERY_PLAN_FILE} to delivery epic ${TARGET_EPIC_ID} through the broker-owned plan/apply route"

pod_name="$(kubectl_cmd -n "${BROKER_NAMESPACE}" get pod -l "app.kubernetes.io/name=operator-orchestration-service" -o jsonpath='{.items[0].metadata.name}')"
plan_remote="/tmp/openproject_delivery_plan.json"

kubectl_cmd -n "${BROKER_NAMESPACE}" cp "${DELIVERY_PLAN_FILE}" "${pod_name}:${plan_remote}"

cleanup() {
  kubectl_cmd -n "${BROKER_NAMESPACE}" exec "${pod_name}" -- rm -f "${plan_remote}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- env \
  TARGET_EPIC_ID="${TARGET_EPIC_ID}" \
  RECONCILE_MISSING="${RECONCILE_MISSING}" \
  RECONCILE_DECISION="${RECONCILE_DECISION}" \
  RECONCILE_RETIREMENT_REASON="${RECONCILE_RETIREMENT_REASON}" \
  RECONCILE_REASON="${RECONCILE_REASON}" \
  RECONCILE_REVIEW_DATE="${RECONCILE_REVIEW_DATE}" \
  BROKER_PORT="${BROKER_PORT}" \
  DELIVERY_PLAN_PATH="${plan_remote}" \
  node --input-type=module - <<'NODE'
import fs from "node:fs";

const brokerPort = process.env.BROKER_PORT || "8080";
const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-apply-delivery-plan";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";
const deliveryId = `delivery-${String(process.env.TARGET_EPIC_ID || "").trim()}`;
const planPath = String(process.env.DELIVERY_PLAN_PATH || "").trim();

if (!planPath) {
  throw new Error("DELIVERY_PLAN_PATH is required");
}

const plan = JSON.parse(fs.readFileSync(planPath, "utf8"));
const input = {
  plan,
};

for (const [envName, fieldName] of [
  ["RECONCILE_MISSING", "reconcile_missing"],
  ["RECONCILE_DECISION", "reconcile_decision"],
  ["RECONCILE_RETIREMENT_REASON", "reconcile_retirement_reason"],
  ["RECONCILE_REASON", "reconcile_reason"],
  ["RECONCILE_REVIEW_DATE", "reconcile_review_date"],
]) {
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

const payload = await requestJson(`${brokerBase}/v1/delivery-initiatives/${deliveryId}/plan/apply`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-correlation-id": `openproject-apply-delivery-plan-${Date.now()}`,
    "x-oos-caller-id": callerId,
    "x-oos-caller-secret": callerSecret,
  },
  body: JSON.stringify({ input }),
});

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
NODE

if [[ -n "${SYNC_PI_NAMES}" ]]; then
  OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
  OPENPROJECT_DELIVERY_PI_NAMES="${SYNC_PI_NAMES}" \
  "${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views.sh" >/dev/null
fi
