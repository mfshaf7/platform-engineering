#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
BROKER_NAMESPACE="${BROKER_NAMESPACE:-operator-orchestration-service}"
BROKER_DEPLOYMENT="${BROKER_DEPLOYMENT:-operator-orchestration-service}"
BROKER_PORT="${BROKER_PORT:-8080}"
OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"
IDEA_ID="${IDEA_ID:-}"
TARGET_PI="${TARGET_PI:-}"
OPERATOR_ID="${OPERATOR_ID:-${USER:-unknown}}"
OPERATOR_HANDLE="${OPERATOR_HANDLE:-${USER:-unknown}}"

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

if [[ -z "${IDEA_ID}" ]]; then
  echo "IDEA_ID is required, for example: make openproject-consume-accepted-idea IDEA_ID=idea-64 TARGET_PI=PI-2026-02 OPERATOR_ID=mfshaf7 OPERATOR_HANDLE=mfshaf7" >&2
  exit 1
fi

echo "Consuming accepted proposal ${IDEA_ID} into ${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}"

kubectl_cmd -n "${BROKER_NAMESPACE}" exec "deploy/${BROKER_DEPLOYMENT}" -- \
  env \
    IDEA_ID="${IDEA_ID}" \
    TARGET_PI="${TARGET_PI}" \
    OPERATOR_ID="${OPERATOR_ID}" \
    OPERATOR_HANDLE="${OPERATOR_HANDLE}" \
    BROKER_PORT="${BROKER_PORT}" \
    OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="${OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER}" \
    node --input-type=module - <<'NODE'
const ideaId = process.env.IDEA_ID;
const targetPi = process.env.TARGET_PI?.trim() || null;
const operatorId = process.env.OPERATOR_ID?.trim();
const operatorHandle = process.env.OPERATOR_HANDLE?.trim() || operatorId;
const brokerPort = process.env.BROKER_PORT || "8080";
const deliveryProjectIdentifier =
  process.env.OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER || "workspace-delivery-art";

if (!ideaId) {
  throw new Error("IDEA_ID is required.");
}

if (!operatorId) {
  throw new Error("OPERATOR_ID is required.");
}

const callerAllowedIds = (process.env.CALLER_ALLOWED_IDS || "")
  .split(",")
  .map((entry) => entry.trim())
  .filter(Boolean);
const callerId = callerAllowedIds[0] || "openproject-consume-script";
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
const deliveryPm2PhaseFieldId = Number.parseInt(
  process.env.OPENPROJECT_DELIVERY_CUSTOM_FIELD_PM2_PHASE_ID || "",
  10,
);
const deliveryTargetPiFieldId = Number.parseInt(
  process.env.OPENPROJECT_DELIVERY_CUSTOM_FIELD_TARGET_PI_ID || "",
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

async function requestJson(url, { method = "GET", headers = {}, body } = {}) {
  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(`${method} ${url} failed with ${response.status}: ${text}`);
  }
  return payload;
}

const runId = `openproject-consume-${Date.now()}`;
const correlationIds = {
  lookup: `${runId}-lookup`,
  consume: `${runId}-consume`,
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

const deliveryProject = await requestJson(
  `${openProjectBaseUrl}/api/v3/projects/${deliveryProjectIdentifier}`,
  { headers: openProjectHeaders() },
);
if (deliveryProject.identifier !== deliveryProjectIdentifier) {
  throw new Error(
    `Delivery project mismatch: expected ${deliveryProjectIdentifier}, got ${deliveryProject.identifier}.`,
  );
}

const consumeBody = {
  operator: {
    id: operatorId,
    handle: operatorHandle,
  },
  input: {},
};
if (targetPi) {
  consumeBody.input.target_pi = targetPi;
}

const consumeResult = await requestJson(
  `${brokerBase}/v1/ideas/${ideaId}/consume`,
  {
    method: "POST",
    headers: brokerHeaders(correlationIds.consume),
    body: consumeBody,
  },
);

const deliveryRef = consumeResult.delivery_ref;
const deliveryRecordIdMatch =
  typeof deliveryRef === "string"
    ? deliveryRef.match(/\/work_packages\/(\d+)$/)
    : null;
if (!deliveryRecordIdMatch) {
  throw new Error(`Consume result does not carry a parseable delivery_ref: ${deliveryRef}`);
}

const sourceRecordId = ideaId.split("-").at(-1);
const sourceRecord = await requestJson(
  `${openProjectBaseUrl}/api/v3/work_packages/${sourceRecordId}`,
  { headers: openProjectHeaders() },
);
const deliveryRecord = await requestJson(
  `${openProjectBaseUrl}/api/v3/work_packages/${deliveryRecordIdMatch[1]}`,
  { headers: openProjectHeaders() },
);
const finalLookup = await requestJson(`${brokerBase}/v1/ideas/${ideaId}`, {
  headers: brokerHeaders(correlationIds.finalLookup),
});

const result = {
  run_id: runId,
  correlation_ids: correlationIds,
  idea_id: ideaId,
  delivery_project: {
    id: deliveryProject.id,
    identifier: deliveryProject.identifier,
    name: deliveryProject.name,
  },
  accepted_idea_lookup: {
    status: acceptedIdea.status,
    record_ref: acceptedIdea.record_ref,
    delivery_ref: acceptedIdea.delivery_ref ?? null,
  },
  consume: consumeResult,
  backlinks: {
    broker_delivery_ref: finalLookup.delivery_ref ?? null,
    source_delivery_ref: Number.isInteger(backlogDeliveryRefFieldId)
      ? readCustomField(sourceRecord, backlogDeliveryRefFieldId)
      : null,
    delivery_origin_idea_ref: Number.isInteger(deliveryOriginIdeaRefFieldId)
      ? readCustomField(deliveryRecord, deliveryOriginIdeaRefFieldId)
      : null,
    delivery_pm2_phase: Number.isInteger(deliveryPm2PhaseFieldId)
      ? readCustomField(deliveryRecord, deliveryPm2PhaseFieldId)
      : null,
    delivery_target_pi: Number.isInteger(deliveryTargetPiFieldId)
      ? readCustomField(deliveryRecord, deliveryTargetPiFieldId)
      : null,
  },
};

console.log(JSON.stringify(result, null, 2));
NODE
