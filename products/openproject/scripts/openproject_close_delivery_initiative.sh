#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
KUBECTL="${KUBECTL:-k3s kubectl}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-operator-orchestration-service}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-${BROKER_NAMESPACE:-openproject}}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
IDEA_ID="${IDEA_ID:-}"
CLOSEOUT_NOTES="${CLOSEOUT_NOTES:-}"
OPERATOR_ID="${OPERATOR_ID:-${USER:-unknown}}"
OPERATOR_HANDLE="${OPERATOR_HANDLE:-${USER:-unknown}}"
CHECK_CLOSEOUT_SCRIPT=""

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

resolve_delivery_epic_id() {
  kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- \
    env \
      IDEA_ID="${IDEA_ID}" \
      BROKER_PORT="${BROKER_PORT}" \
      node --input-type=module - <<'NODE'
const ideaId = process.env.IDEA_ID;
const brokerPort = process.env.BROKER_PORT || "8080";

if (!ideaId) {
  throw new Error("IDEA_ID is required.");
}

const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-closeout-lookup";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";

const response = await fetch(`http://127.0.0.1:${brokerPort}/v1/ideas/${ideaId}`, {
  method: "GET",
  headers: {
    "x-oos-caller-id": callerId,
    "x-oos-caller-secret": callerSecret,
    "x-correlation-id": `openproject-closeout-lookup-${Date.now()}`,
  },
});
const text = await response.text();
if (!response.ok) {
  throw new Error(`GET /v1/ideas/${ideaId} failed: ${response.status} ${text}`);
}
const payload = text ? JSON.parse(text) : null;
const deliveryRef = payload?.delivery_ref;
const match =
  typeof deliveryRef === "string"
    ? deliveryRef.match(/\/work_packages\/(\d+)$/)
    : null;
if (!match) {
  throw new Error(`Idea ${ideaId} does not carry a parseable delivery_ref: ${deliveryRef}`);
}
process.stdout.write(`${match[1]}\n`);
NODE
}

need_cmd "${KUBECTL%% *}"

if [[ -z "${IDEA_ID}" ]]; then
  echo "IDEA_ID is required, for example: make openproject-close-delivery-initiative IDEA_ID=idea-37 CLOSEOUT_NOTES='Delivered through PI-2026-02' OPERATOR_ID=mfshaf7 OPERATOR_HANDLE=mfshaf7" >&2
  exit 1
fi

if [[ -z "${CLOSEOUT_NOTES}" ]]; then
  echo "CLOSEOUT_NOTES is required, for example: make openproject-close-delivery-initiative IDEA_ID=idea-37 CLOSEOUT_NOTES='Delivered through PI-2026-02' OPERATOR_ID=mfshaf7 OPERATOR_HANDLE=mfshaf7" >&2
  exit 1
fi

echo "Closing delivery initiative for ${IDEA_ID}"

CHECK_CLOSEOUT_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_check_delivery_closeout_readiness.sh"
if [[ ! -f "${CHECK_CLOSEOUT_SCRIPT}" ]]; then
  echo "Missing readiness script: ${CHECK_CLOSEOUT_SCRIPT}" >&2
  exit 1
fi

delivery_epic_id="$(resolve_delivery_epic_id | tail -n 1)"
if [[ -z "${delivery_epic_id}" ]]; then
  echo "Unable to resolve delivery epic id for ${IDEA_ID}" >&2
  exit 1
fi

echo "Verifying closeout readiness for delivery epic ${delivery_epic_id}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
TARGET_EPIC_ID="${delivery_epic_id}" \
"${CHECK_CLOSEOUT_SCRIPT}"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec -i "deploy/${BROKER_DEPLOYMENT}" -- \
  env \
    IDEA_ID="${IDEA_ID}" \
    CLOSEOUT_NOTES="${CLOSEOUT_NOTES}" \
    OPERATOR_ID="${OPERATOR_ID}" \
    OPERATOR_HANDLE="${OPERATOR_HANDLE}" \
    BROKER_PORT="${BROKER_PORT}" \
    node --input-type=module - <<'NODE'
import http from "node:http";
import https from "node:https";

const ideaId = process.env.IDEA_ID;
const closeoutNotes = process.env.CLOSEOUT_NOTES?.trim();
const operatorId = process.env.OPERATOR_ID?.trim();
const operatorHandle = process.env.OPERATOR_HANDLE?.trim() || operatorId;
const brokerPort = process.env.BROKER_PORT || "8080";

if (!ideaId) {
  throw new Error("IDEA_ID is required.");
}

if (!closeoutNotes) {
  throw new Error("CLOSEOUT_NOTES is required.");
}

if (!operatorId) {
  throw new Error("OPERATOR_ID is required.");
}

const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-closeout-script";
const callerSecret = process.env.CALLER_AUTH_SHARED_SECRET || "";
const openProjectBaseUrl = process.env.OPENPROJECT_BASE_URL;
const openProjectHostHeader = process.env.OPENPROJECT_HOST_HEADER || "";
const openProjectApiToken = process.env.OPENPROJECT_API_TOKEN;
const backlogDeliveryRefFieldId = Number.parseInt(
  process.env.OPENPROJECT_CUSTOM_FIELD_DELIVERY_REF_ID || "",
  10,
);
const deliveryOriginIdeaRefFieldId = Number.parseInt(
  process.env.OPENPROJECT_DELIVERY_CUSTOM_FIELD_ORIGIN_IDEA_REF_ID || "",
  10,
);

if (!openProjectBaseUrl || !openProjectApiToken) {
  throw new Error("OpenProject runtime config is incomplete in the live broker environment.");
}

function brokerHeaders(correlationId) {
  return {
    "Content-Type": "application/json",
    "x-oos-caller-id": callerId,
    "x-oos-caller-secret": callerSecret,
    "x-correlation-id": correlationId,
  };
}

function openProjectHeaders() {
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${openProjectApiToken}`,
    "Content-Type": "application/json",
  };
  if (openProjectHostHeader) {
    headers.Host = openProjectHostHeader;
  }
  return headers;
}

function readCustomField(payload, fieldId) {
  const key = `customField${fieldId}`;
  if (Object.prototype.hasOwnProperty.call(payload, key)) {
    return payload[key];
  }

  const linked = payload?._links?.[key];
  if (Array.isArray(linked)) {
    return linked
      .map((entry) =>
        entry && typeof entry.title === "string" ? entry.title.trim() : "",
      )
      .filter(Boolean);
  }
  if (linked && typeof linked.title === "string" && linked.title.trim()) {
    return linked.title.trim();
  }
  return null;
}

function readStatus(payload) {
  return payload?._links?.status?.title || payload?.status || null;
}

async function requestJson(url, { method = "GET", headers = {}, body } = {}) {
  const parsedUrl = new URL(url);
  const transport = parsedUrl.protocol === "https:" ? https : http;
  const requestBody =
    body === undefined ? undefined : JSON.stringify(body);
  const response = await new Promise((resolve, reject) => {
    const request = transport.request(
      parsedUrl,
      {
        agent: false,
        headers,
        method,
      },
      (incoming) => {
        const chunks = [];

        incoming.on("data", (chunk) => {
          chunks.push(chunk);
        });

        incoming.on("end", () => {
          resolve({
            ok:
              typeof incoming.statusCode === "number" &&
              incoming.statusCode >= 200 &&
              incoming.statusCode < 300,
            status: incoming.statusCode ?? 0,
            text: Buffer.concat(chunks).toString("utf8"),
          });
        });
      },
    );

    request.on("error", reject);

    if (requestBody) {
      request.write(requestBody);
    }

    request.end();
  });
  const payload = response.text ? JSON.parse(response.text) : null;
  if (!response.ok) {
    throw new Error(`${method} ${url} failed with ${response.status}: ${response.text}`);
  }
  return payload;
}

const runId = `openproject-closeout-${Date.now()}`;
const correlationIds = {
  lookup: `${runId}-lookup`,
  closeout: `${runId}-closeout`,
  finalLookup: `${runId}-final-lookup`,
};

const brokerBase = `http://127.0.0.1:${brokerPort}`;
const ready = await requestJson(`${brokerBase}/readyz`);
if (!ready.ready) {
  throw new Error(`Broker is not ready: ${JSON.stringify(ready)}`);
}

const acceptedIdea = await requestJson(`${brokerBase}/v1/ideas/${ideaId}`, {
  headers: brokerHeaders(correlationIds.lookup),
});
if (acceptedIdea.status !== "accepted") {
  throw new Error(
    `Idea ${ideaId} is not accepted; current status is ${acceptedIdea.status}.`,
  );
}

const deliveryRef = acceptedIdea.delivery_ref;
const deliveryRecordIdMatch =
  typeof deliveryRef === "string"
    ? deliveryRef.match(/\/work_packages\/(\d+)$/)
    : null;
if (!deliveryRecordIdMatch) {
  throw new Error(`Accepted idea does not carry a parseable delivery_ref: ${deliveryRef}`);
}

const deliveryRecordBefore = await requestJson(
  `${openProjectBaseUrl}/api/v3/work_packages/${deliveryRecordIdMatch[1]}`,
  { headers: openProjectHeaders() },
);
if (readStatus(deliveryRecordBefore) !== "done") {
  throw new Error(
    `Delivery record ${deliveryRef} is ${readStatus(deliveryRecordBefore)} and cannot be closed yet.`,
  );
}
if (
  Number.isInteger(deliveryOriginIdeaRefFieldId) &&
  readCustomField(deliveryRecordBefore, deliveryOriginIdeaRefFieldId) !== ideaId
) {
  throw new Error(
    `Delivery origin backlink mismatch for ${deliveryRef}.`,
  );
}

const closeoutResult = await requestJson(
  `${brokerBase}/v1/ideas/${ideaId}/closeout`,
  {
    method: "POST",
    headers: brokerHeaders(correlationIds.closeout),
    body: {
      operator: {
        id: operatorId,
        handle: operatorHandle,
      },
      input: {
        closeout_notes: closeoutNotes,
      },
    },
  },
);

const sourceRecordId = ideaId.split("-").at(-1);
const sourceRecord = await requestJson(
  `${openProjectBaseUrl}/api/v3/work_packages/${sourceRecordId}`,
  { headers: openProjectHeaders() },
);
const finalLookup = await requestJson(`${brokerBase}/v1/ideas/${ideaId}`, {
  headers: brokerHeaders(correlationIds.finalLookup),
});

if (finalLookup.status !== "implemented") {
  throw new Error(`Closeout did not move ${ideaId} to implemented: ${JSON.stringify(finalLookup)}`);
}

const result = {
  run_id: runId,
  correlation_ids: correlationIds,
  idea_id: ideaId,
  accepted_idea_lookup: {
    status: acceptedIdea.status,
    record_ref: acceptedIdea.record_ref,
    delivery_ref: acceptedIdea.delivery_ref ?? null,
  },
  closeout: closeoutResult,
  final_projection: {
    status: finalLookup.status,
    delivery_ref: finalLookup.delivery_ref ?? null,
    delivery_closeout_notes: finalLookup.delivery_closeout_notes ?? null,
  },
  source_record: {
    record_ref: `openproject://work_packages/${sourceRecord.id}`,
    status: readStatus(sourceRecord),
    delivery_ref: Number.isInteger(backlogDeliveryRefFieldId)
      ? readCustomField(sourceRecord, backlogDeliveryRefFieldId)
      : null,
  },
  delivery_record: {
    record_ref: deliveryRef,
    status: readStatus(deliveryRecordBefore),
    origin_idea_ref: Number.isInteger(deliveryOriginIdeaRefFieldId)
      ? readCustomField(deliveryRecordBefore, deliveryOriginIdeaRefFieldId)
      : null,
  },
};

console.log(JSON.stringify(result, null, 2));
NODE
