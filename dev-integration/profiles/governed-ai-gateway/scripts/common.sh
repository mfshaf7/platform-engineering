#!/usr/bin/env bash
set -euo pipefail

readonly PROFILE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly OWNER_REPO_ROOT="$(cd "${PROFILE_ROOT}/../../.." && pwd)"
readonly PROFILE_ID="${DEVINT_PROFILE_ID:-governed-ai-gateway}"
readonly OPERATOR="${DEVINT_OPERATOR:-${USER:-operator}}"
readonly NAMESPACE="${DEVINT_NAMESPACE:-devint-${PROFILE_ID}-${OPERATOR}}"
readonly CONSUMER_NAMESPACE="${DEVINT_GAI_CONSUMER_NAMESPACE:-${NAMESPACE}-consumer}"
readonly PROVIDER_NAMESPACE="${DEVINT_GAI_PROVIDER_NAMESPACE:-${NAMESPACE}-provider-sentinel}"
readonly STATE_ROOT="${DEVINT_STATE_ROOT:-${OWNER_REPO_ROOT}/.dev-integration/${PROFILE_ID}/${OPERATOR}}"
readonly SESSION_FILE="${DEVINT_SESSION_FILE:-${STATE_ROOT}/session.yaml}"
readonly PROMOTION_REPORT="${DEVINT_PROMOTION_REPORT:-${STATE_ROOT}/promotion-report.yaml}"
readonly DEVINT_KUBECONFIG_PATH="${DEVINT_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

export KUBECONFIG="${DEVINT_KUBECONFIG_PATH}"

read -r -a KUBECTL_CMD <<<"${DEVINT_KUBECTL:-k3s kubectl}"

readonly STATUS_FILE="${STATE_ROOT}/profile-status.txt"
readonly SMOKE_SUMMARY="${STATE_ROOT}/smoke-summary.json"
readonly MODEL_SELECTION_RECEIPT="${STATE_ROOT}/model-binding-selection.json"
readonly PROFILE_PROMOTION_NOTES="${STATE_ROOT}/profile-promotion-notes.md"
readonly RENDERED_DIR="${STATE_ROOT}/rendered"
readonly LOGS_DIR="${STATE_ROOT}/logs"
readonly ACCESS_LOCAL_PORT="${DEVINT_GAI_GATEWAY_LOCAL_PORT:-18290}"
readonly RUNTIME_SOURCE_DIR="${PROFILE_ROOT}/runtime"
readonly MODEL_PROFILE_ID_REQUESTED="${DEVINT_GAI_MODEL_PROFILE_ID:-intake-classifier-v1}"
readonly MODEL_ENVIRONMENT_REQUESTED="${DEVINT_GAI_MODEL_ENVIRONMENT:-dev-integration}"

readonly GATEWAY_DEPLOYMENT="governed-ai-gateway"
readonly GATEWAY_SERVICE="governed-ai-gateway"
readonly GATEWAY_PVC="governed-ai-gateway-audit"
readonly GATEWAY_CONFIGMAP="governed-ai-gateway-app"
readonly CONSUMER_DEPLOYMENT="governed-ai-consumer-probe"
readonly PROVIDER_DEPLOYMENT="direct-provider-sentinel"
readonly PROVIDER_SERVICE="direct-provider-sentinel"

kubectl_cmd() {
  "${KUBECTL_CMD[@]}" "$@"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_state_dirs() {
  mkdir -p "${STATE_ROOT}" "${RENDERED_DIR}" "${LOGS_DIR}"
}

profile_lifecycle() {
  if [[ -n "${DEVINT_PROFILE_LIFECYCLE:-}" ]]; then
    printf '%s' "${DEVINT_PROFILE_LIFECYCLE}"
    return
  fi

  if [[ -f "${SESSION_FILE}" ]]; then
    python3 - "${SESSION_FILE}" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
match = re.search(r"(?m)^profile_lifecycle:\s*['\"]?([^'\"\n]+)['\"]?\s*$", text)
print(match.group(1).strip() if match else "build-admitted")
PY
    return
  fi

  printf 'build-admitted'
}

readonly PROFILE_LIFECYCLE="$(profile_lifecycle)"

load_model_binding() {
  python3 "${RUNTIME_SOURCE_DIR}/model_profile_resolver.py" \
    --profile-registry "${OWNER_REPO_ROOT}/security/governed-ai-model-profiles.yaml" \
    --access-plane "${OWNER_REPO_ROOT}/security/governed-ai-access-plane.yaml" \
    --profile-id "${MODEL_PROFILE_ID_REQUESTED}" \
    --environment "${MODEL_ENVIRONMENT_REQUESTED}"
}

MODEL_SELECTION_JSON="$(load_model_binding)"
readonly MODEL_SELECTION_JSON
mapfile -t MODEL_BINDING < <(
  python3 -c '
import json
import sys

selection = json.load(sys.stdin)
fields = (
    "profile_status",
    "profile_id",
    "environment",
    "binding_id",
    "binding_status",
    "provider",
    "provider_route",
    "provider_route_status",
    "upstream_model",
    "model_digest",
    "runtime_version",
    "endpoint_origin",
    "provider_output_schema_ref",
    "selection_digest",
    "selection_ref",
    "profile_registry_digest",
    "access_plane_digest",
    "invocation_path",
    "purpose",
    "fallback_mode",
    "activation_eligible",
)
for field in fields:
    value = selection[field]
    if isinstance(value, bool):
        print("true" if value else "false")
    else:
        print(value)
print(",".join(selection["allowed_callers"]))
print("true" if selection["profile_activation_allowed"] else "false")
' <<<"${MODEL_SELECTION_JSON}"
)
if [[ "${#MODEL_BINDING[@]}" -ne 23 ]]; then
  echo "Unable to resolve governed AI model binding" >&2
  exit 1
fi
readonly MODEL_PROFILE_STATUS="${MODEL_BINDING[0]}"
readonly MODEL_PROFILE_ID="${MODEL_BINDING[1]}"
readonly MODEL_ENVIRONMENT="${MODEL_BINDING[2]}"
readonly MODEL_BINDING_ID="${MODEL_BINDING[3]}"
readonly MODEL_BINDING_STATUS="${MODEL_BINDING[4]}"
readonly UPSTREAM_PROVIDER="${MODEL_BINDING[5]}"
readonly UPSTREAM_PROVIDER_ROUTE="${MODEL_BINDING[6]}"
readonly MODEL_PROVIDER_ROUTE_STATUS="${MODEL_BINDING[7]}"
readonly UPSTREAM_MODEL="${MODEL_BINDING[8]}"
readonly UPSTREAM_MODEL_DIGEST="${MODEL_BINDING[9]}"
readonly PROVIDER_RUNTIME_VERSION="${MODEL_BINDING[10]}"
readonly PROVIDER_BASE_URL="${MODEL_BINDING[11]}"
readonly PROVIDER_OUTPUT_SCHEMA_REF="${MODEL_BINDING[12]}"
readonly MODEL_SELECTION_DIGEST="${MODEL_BINDING[13]}"
readonly MODEL_SELECTION_REF="${MODEL_BINDING[14]}"
readonly MODEL_PROFILE_REGISTRY_DIGEST="${MODEL_BINDING[15]}"
readonly MODEL_ACCESS_PLANE_DIGEST="${MODEL_BINDING[16]}"
readonly INVOCATION_PATH="${MODEL_BINDING[17]}"
readonly MODEL_PROFILE_PURPOSE="${MODEL_BINDING[18]}"
readonly MODEL_FALLBACK_MODE="${MODEL_BINDING[19]}"
readonly MODEL_ACTIVATION_ELIGIBLE="${MODEL_BINDING[20]}"
readonly ALLOWED_CALLERS_CSV="${MODEL_BINDING[21]}"
readonly ACCESS_PLANE_ACTIVATION_ALLOWED="${MODEL_BINDING[22]}"

is_active_profile() {
  [[ "${PROFILE_LIFECYCLE}" == "active" ]]
}

render_status() {
  cat <<EOF
profile: ${PROFILE_ID}
lifecycle: ${PROFILE_LIFECYCLE}
namespace: ${NAMESPACE}
consumer namespace: ${CONSUMER_NAMESPACE}
provider sentinel namespace: ${PROVIDER_NAMESPACE}
operator: ${OPERATOR}
state root: ${STATE_ROOT}
runtime: $(is_active_profile && printf 'active-local-k3s' || printf 'build-admitted-not-active')
launchable: $(is_active_profile && printf 'true' || printf 'false')
gateway service: ${GATEWAY_SERVICE}
gateway local port: ${ACCESS_LOCAL_PORT}
model profile: ${MODEL_PROFILE_ID}
model profile status: ${MODEL_PROFILE_STATUS}
model environment: ${MODEL_ENVIRONMENT}
model binding: ${MODEL_BINDING_ID}
model binding status: ${MODEL_BINDING_STATUS}
model selection ref: ${MODEL_SELECTION_REF}
model selection digest: ${MODEL_SELECTION_DIGEST}
model fallback mode: ${MODEL_FALLBACK_MODE}
model activation eligible: ${MODEL_ACTIVATION_ELIGIBLE}
access plane activation allowed: ${ACCESS_PLANE_ACTIVATION_ALLOWED}
upstream provider: ${UPSTREAM_PROVIDER}
provider route: ${UPSTREAM_PROVIDER_ROUTE}
provider route status: ${MODEL_PROVIDER_ROUTE_STATUS}
upstream model: ${UPSTREAM_MODEL}
upstream model digest: ${UPSTREAM_MODEL_DIGEST}
provider runtime version: ${PROVIDER_RUNTIME_VERSION}
EOF
}

write_status_file() {
  ensure_state_dirs
  render_status >"${STATUS_FILE}"
}

write_model_selection_receipt() {
  ensure_state_dirs
  printf '%s\n' "${MODEL_SELECTION_JSON}" >"${MODEL_SELECTION_RECEIPT}"
}

print_status() {
  render_status
}

fail_not_active() {
  write_status_file
  cat "${STATUS_FILE}"
  echo
  echo "refused: ${PROFILE_ID} is ${PROFILE_LIFECYCLE}, not active; governed AI gateway runtime launch is intentionally blocked." >&2
  exit 2
}

require_active_profile() {
  if ! is_active_profile; then
    fail_not_active
  fi
}

require_active_model_binding() {
  if [[ "${MODEL_ACTIVATION_ELIGIBLE}" != "true" ]]; then
    echo "refused: selected model binding ${MODEL_SELECTION_REF} is not activation eligible." >&2
    exit 2
  fi
}

wait_for_runtime_ready() {
  kubectl_cmd -n "${PROVIDER_NAMESPACE}" rollout status "deployment/${PROVIDER_DEPLOYMENT}" --timeout=300s
  kubectl_cmd -n "${NAMESPACE}" rollout status "deployment/${GATEWAY_DEPLOYMENT}" --timeout=300s
  kubectl_cmd -n "${CONSUMER_NAMESPACE}" rollout status "deployment/${CONSUMER_DEPLOYMENT}" --timeout=300s
}

render_gateway_app() {
  cat >"${RENDERED_DIR}/gateway_app.py" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ollama_adapter import OllamaAdapter, OllamaAdapterError

AUDIT_ROOT = Path(os.environ.get("GOVERNED_AI_AUDIT_ROOT", "/var/lib/governed-ai-gateway"))
AUDIT_LEDGER = AUDIT_ROOT / "audit-ledger.jsonl"
PROFILE_ID = os.environ.get("GOVERNED_AI_PROFILE_ID", "intake-classifier-v1")
PROFILE_STATUS = os.environ.get("GOVERNED_AI_PROFILE_STATUS", "suspended")
PROFILE_PURPOSE = os.environ.get("GOVERNED_AI_PROFILE_PURPOSE", "unbound")
MODEL_ENVIRONMENT = os.environ.get("GOVERNED_AI_MODEL_ENVIRONMENT", "unbound")
BINDING_ID = os.environ.get("GOVERNED_AI_BINDING_ID", "unbound")
BINDING_STATUS = os.environ.get("GOVERNED_AI_BINDING_STATUS", "unbound")
BINDING_SELECTION_DIGEST = os.environ.get(
    "GOVERNED_AI_BINDING_SELECTION_DIGEST", "unbound"
)
BINDING_SELECTION_REF = os.environ.get("GOVERNED_AI_BINDING_SELECTION_REF", "unbound")
PROFILE_REGISTRY_DIGEST = os.environ.get("GOVERNED_AI_PROFILE_REGISTRY_DIGEST", "unbound")
ACCESS_PLANE_DIGEST = os.environ.get("GOVERNED_AI_ACCESS_PLANE_DIGEST", "unbound")
FALLBACK_MODE = os.environ.get(
    "GOVERNED_AI_FALLBACK_MODE", "fail-closed-no-implicit-fallback"
)
MODEL_ACTIVATION_ELIGIBLE = (
    os.environ.get("GOVERNED_AI_MODEL_ACTIVATION_ELIGIBLE", "false").lower()
    == "true"
)
ACCESS_PLANE_ACTIVATION_ALLOWED = (
    os.environ.get("GOVERNED_AI_ACCESS_PLANE_ACTIVATION_ALLOWED", "false").lower()
    == "true"
)
UPSTREAM_PROVIDER = os.environ.get("GOVERNED_AI_UPSTREAM_PROVIDER", "unbound")
UPSTREAM_PROVIDER_ROUTE = os.environ.get("GOVERNED_AI_UPSTREAM_PROVIDER_ROUTE", "unbound")
PROVIDER_ROUTE_STATUS = os.environ.get("GOVERNED_AI_PROVIDER_ROUTE_STATUS", "unbound")
UPSTREAM_MODEL = os.environ.get("GOVERNED_AI_UPSTREAM_MODEL", "unbound")
UPSTREAM_MODEL_DIGEST = os.environ.get("GOVERNED_AI_UPSTREAM_MODEL_DIGEST", "unbound")
PROVIDER_RUNTIME_VERSION = os.environ.get("GOVERNED_AI_PROVIDER_RUNTIME_VERSION", "unbound")
PROVIDER_BASE_URL = os.environ.get("GOVERNED_AI_PROVIDER_BASE_URL", "http://host.docker.internal:11434")
INVOCATION_PATH = os.environ.get("GOVERNED_AI_INVOCATION_PATH", "governed-ai-gateway")
OUTPUT_SCHEMA_REF = os.environ.get(
    "GOVERNED_AI_OUTPUT_SCHEMA_REF",
    "platform-engineering/security/schemas/intake-classification-result.schema.json",
)
ALLOWED_CALLERS = {
    caller
    for caller in os.environ.get(
        "GOVERNED_AI_ALLOWED_CALLERS", "workspace-governance/intake-assist"
    ).split(",")
    if caller
}
MAX_REQUEST_BYTES = int(os.environ.get("GOVERNED_AI_MAX_REQUEST_BYTES", "16384"))

PROVIDER = OllamaAdapter(
    base_url=PROVIDER_BASE_URL,
    model=UPSTREAM_MODEL,
    expected_digest=UPSTREAM_MODEL_DIGEST,
    expected_runtime_version=PROVIDER_RUNTIME_VERSION,
    timeout_seconds=float(os.environ.get("GOVERNED_AI_PROVIDER_TIMEOUT_SECONDS", "30")),
    retry_count=int(os.environ.get("GOVERNED_AI_PROVIDER_RETRY_COUNT", "1")),
    max_concurrency=int(os.environ.get("GOVERNED_AI_PROVIDER_MAX_CONCURRENCY", "2")),
    max_output_tokens=int(os.environ.get("GOVERNED_AI_PROVIDER_MAX_OUTPUT_TOKENS", "64")),
)

REQUIRED_CALLER_FIELDS = [
    "caller_id",
    "caller_repo",
    "caller_workflow",
    "decision_or_correlation_id",
    "requested_profile_id",
]
def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def audit_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def append_audit(event: dict) -> dict:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event["event_time"] = utc_now()
    event["event_digest"] = audit_digest(event)
    with AUDIT_LEDGER.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def latest_audit_event() -> dict:
    if not AUDIT_LEDGER.exists():
        return {"event_count": 0, "latest": None}
    lines = [line for line in AUDIT_LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        "event_count": len(lines),
        "latest": json.loads(lines[-1]) if lines else None,
    }


def selected_binding_evidence() -> dict:
    return {
        "profile_id": PROFILE_ID,
        "profile_status": PROFILE_STATUS,
        "environment": MODEL_ENVIRONMENT,
        "binding_id": BINDING_ID,
        "binding_status": BINDING_STATUS,
        "provider": UPSTREAM_PROVIDER,
        "provider_route": UPSTREAM_PROVIDER_ROUTE,
        "provider_route_status": PROVIDER_ROUTE_STATUS,
        "upstream_model": UPSTREAM_MODEL,
        "upstream_model_digest": UPSTREAM_MODEL_DIGEST,
        "provider_runtime_version": PROVIDER_RUNTIME_VERSION,
        "profile_registry_digest": PROFILE_REGISTRY_DIGEST,
        "access_plane_digest": ACCESS_PLANE_DIGEST,
        "selection_digest": BINDING_SELECTION_DIGEST,
        "selection_ref": BINDING_SELECTION_REF,
        "fallback_mode": FALLBACK_MODE,
        "activation_eligible": MODEL_ACTIVATION_ELIGIBLE,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "GovernedAIGatewayDevInt/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        if length > MAX_REQUEST_BYTES:
            raise ValueError("request-too-large")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request-must-be-object")
        return payload

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.send_json(200, {"status": "ok", "component": "governed-ai-gateway"})
            return
        if self.path == "/readyz":
            ready = MODEL_ACTIVATION_ELIGIBLE and ACCESS_PLANE_ACTIVATION_ALLOWED
            self.send_json(
                200 if ready else 503,
                {
                    "ready": ready,
                    "profile_id": PROFILE_ID,
                    "profile_status": PROFILE_STATUS,
                    "access_plane_activation_allowed": ACCESS_PLANE_ACTIVATION_ALLOWED,
                    "upstream_provider": UPSTREAM_PROVIDER,
                    "provider_route": UPSTREAM_PROVIDER_ROUTE,
                    "upstream_model": UPSTREAM_MODEL,
                    "upstream_model_digest": UPSTREAM_MODEL_DIGEST,
                    "provider_runtime_version": PROVIDER_RUNTIME_VERSION,
                    "selected_binding": selected_binding_evidence(),
                    "provider_credential_required": False,
                    "raw_provider_token_projected": False,
                },
            )
            return
        if self.path == "/v1/provider/custody":
            self.send_json(
                200,
                {
                    "provider_credential_required": False,
                    "provider_secret_available": False,
                    "upstream_provider": UPSTREAM_PROVIDER,
                    "provider_route": UPSTREAM_PROVIDER_ROUTE,
                    "upstream_model": UPSTREAM_MODEL,
                    "provider_secret_ref": None,
                    "consumer_provider_credentials_allowed": False,
                    "provider_secret_projected_to_consumers": False,
                    "token_value_projected": False,
                },
            )
            return
        if self.path == "/v1/audit/events/latest":
            self.send_json(200, latest_audit_event())
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/v1/governed-ai/invoke":
            self.send_json(404, {"error": "not_found"})
            return

        try:
            request = self.read_json()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.send_json(400, {"error": "invalid-request", "reason": str(exc)})
            return
        caller_identity = request.get("caller_identity") or {}
        missing = [field for field in REQUIRED_CALLER_FIELDS if not caller_identity.get(field)]
        requested_profile = request.get("profile_id") or caller_identity.get("requested_profile_id")
        output_schema_ref = request.get("provider_output_schema_ref")
        operator_identity = request.get("operator_identity") or {}
        operator_acceptance_state = request.get("operator_acceptance_state", "not-recorded")

        denial_reasons: list[str] = []
        if missing:
            denial_reasons.append("missing-caller-identity:" + ",".join(missing))
        if caller_identity.get("caller_id") not in ALLOWED_CALLERS:
            denial_reasons.append("caller-not-allowed")
        if requested_profile != PROFILE_ID:
            denial_reasons.append("profile-not-allowed")
        if PROFILE_STATUS != "active":
            denial_reasons.append("profile-not-active")
        if BINDING_STATUS != "active":
            denial_reasons.append("binding-not-active")
        if PROVIDER_ROUTE_STATUS != "active":
            denial_reasons.append("provider-route-not-active")
        if not ACCESS_PLANE_ACTIVATION_ALLOWED:
            denial_reasons.append("access-plane-not-active")
        if not MODEL_ACTIVATION_ELIGIBLE:
            denial_reasons.append("model-selection-not-activation-eligible")
        if UPSTREAM_MODEL == "pending-selection":
            denial_reasons.append("upstream-model-pending-selection")
        if output_schema_ref != OUTPUT_SCHEMA_REF:
            denial_reasons.append("output-schema-mismatch")
        if not operator_identity.get("operator_id"):
            denial_reasons.append("operator-identity-missing")

        intake_packet = request.get("input") or {}
        if not isinstance(intake_packet, dict):
            denial_reasons.append("input-must-be-object")
            intake_packet = {}
        allowed_input_fields = {"operator_supplied_intake_notes", "model_safe_packet"}
        if set(intake_packet).difference(allowed_input_fields):
            denial_reasons.append("input-field-not-allowed")
        note = intake_packet.get("operator_supplied_intake_notes")
        if not isinstance(note, str) or not note.strip():
            denial_reasons.append("intake-notes-missing")
        model_safe_packet = intake_packet.get("model_safe_packet")
        if model_safe_packet is not None:
            required_packet_fields = {"packet_ref", "redaction_receipt_ref", "content"}
            if not isinstance(model_safe_packet, dict) or not all(
                isinstance(model_safe_packet.get(field), str) and model_safe_packet.get(field)
                for field in required_packet_fields
            ):
                denial_reasons.append("model-safe-packet-invalid")

        policy_decision = "deny" if denial_reasons else "allow"
        correlation_id = caller_identity.get("decision_or_correlation_id") or request.get("correlation_id")
        event_base = {
                "correlation_id": correlation_id,
                "caller_identity": caller_identity,
                "operator_identity": operator_identity,
                "approved_profile_id": PROFILE_ID,
                "selected_binding": selected_binding_evidence(),
                "access_plane_activation_allowed": ACCESS_PLANE_ACTIVATION_ALLOWED,
                "requested_profile_id": requested_profile,
                "invocation_path": INVOCATION_PATH,
                "upstream_provider": UPSTREAM_PROVIDER,
                "provider_route": UPSTREAM_PROVIDER_ROUTE,
                "upstream_model": UPSTREAM_MODEL,
                "upstream_model_digest": UPSTREAM_MODEL_DIGEST,
                "provider_runtime_version": PROVIDER_RUNTIME_VERSION,
                "prompt_version": PROVIDER.prompt_version,
                "purpose": PROFILE_PURPOSE,
                "output_schema_ref": OUTPUT_SCHEMA_REF,
                "policy_decision": policy_decision,
                "policy_reasons": denial_reasons,
                "operator_acceptance_state": operator_acceptance_state,
                "override_reason": request.get("override_reason"),
                "model_safe_packet_ref": (model_safe_packet or {}).get("packet_ref"),
                "redaction_receipt_ref": (model_safe_packet or {}).get("redaction_receipt_ref"),
                "provider_secret_ref": None,
                "provider_secret_projected": False,
        }

        if denial_reasons:
            event = append_audit(
                {
                    **event_base,
                    "outcome": "denied",
                    "provider_schema_valid": False,
                    "provider_latency_ms": 0,
                    "provider_usage": {},
                }
            )
            self.send_json(
                403,
                {
                    "policy_decision": "deny",
                    "reasons": denial_reasons,
                    "audit_ref": f"local-ledger:{event['event_digest']}",
                },
            )
            return

        try:
            provider_result = PROVIDER.classify(intake_packet)
        except OllamaAdapterError as exc:
            event = append_audit(
                {
                    **event_base,
                    "outcome": exc.code,
                    "provider_schema_valid": False,
                    "provider_latency_ms": 0,
                    "provider_usage": {},
                }
            )
            status = 504 if exc.code == "provider-timeout" else 503
            self.send_json(
                status,
                {
                    "policy_decision": "deny",
                    "reasons": [exc.code],
                    "audit_ref": f"local-ledger:{event['event_digest']}",
                },
            )
            return

        event = append_audit(
            {
                **event_base,
                "upstream_model_digest": provider_result.model_digest,
                "provider_runtime_version": provider_result.runtime_version,
                "outcome": "suggestion-produced",
                "provider_schema_valid": True,
                "provider_latency_ms": provider_result.latency_ms,
                "provider_usage": provider_result.usage,
            }
        )

        self.send_json(
            200,
            {
                "profile_id": PROFILE_ID,
                "policy_status": PROFILE_STATUS,
                "policy_decision": "allow",
                "decision_id": correlation_id,
                "generated_at": event["event_time"],
                "confidence": provider_result.output["confidence"],
                "caller_id": caller_identity.get("caller_id"),
                "invocation_path": INVOCATION_PATH,
                "binding_selection_ref": BINDING_SELECTION_REF,
                "suggested_decision": provider_result.output["suggested_decision"],
                "audit_ref": f"local-ledger:{event['event_digest']}",
            },
        )


def main() -> None:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
PY
}

render_provider_sentinel_app() {
  cat >"${RENDERED_DIR}/provider_sentinel.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        body = json.dumps({"status": "reachable", "component": "direct-provider-sentinel"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
PY
}

render_runtime_manifest() {
  ensure_state_dirs
  write_model_selection_receipt
  if [[ "${UPSTREAM_PROVIDER}" != "ollama" ]]; then
    echo "No governed-ai-gateway runtime adapter is implemented for provider ${UPSTREAM_PROVIDER}" >&2
    exit 1
  fi
  render_gateway_app
  render_provider_sentinel_app
  cp "${RUNTIME_SOURCE_DIR}/ollama_adapter.py" "${RENDERED_DIR}/ollama_adapter.py"

  local provider_host_ip
  provider_host_ip="${DEVINT_GAI_PROVIDER_HOST_IP:-}"
  if [[ -z "${provider_host_ip}" ]]; then
    provider_host_ip="$(getent hosts host.docker.internal | awk 'NR == 1 {print $1}')"
  fi
  if [[ -z "${provider_host_ip}" ]]; then
    echo "Unable to resolve host.docker.internal for governed AI provider route" >&2
    exit 1
  fi

  cat >"${RENDERED_DIR}/governed-ai-gateway-runtime.yaml" <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${NAMESPACE}
  labels:
    governed-ai-gateway: "true"
    dev-integration-profile: ${PROFILE_ID}
---
apiVersion: v1
kind: Namespace
metadata:
  name: ${CONSUMER_NAMESPACE}
  labels:
    governed-ai-consumer: "true"
    dev-integration-profile: ${PROFILE_ID}
---
apiVersion: v1
kind: Namespace
metadata:
  name: ${PROVIDER_NAMESPACE}
  labels:
    governed-ai-provider-sentinel: "true"
    dev-integration-profile: ${PROFILE_ID}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${GATEWAY_PVC}
  namespace: ${NAMESPACE}
  labels:
    dev-integration-profile: ${PROFILE_ID}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: ${DEVINT_GAI_AUDIT_VOLUME_SIZE:-1Gi}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${GATEWAY_CONFIGMAP}
  namespace: ${NAMESPACE}
  labels:
    dev-integration-profile: ${PROFILE_ID}
data:
  gateway_app.py: |
$(sed 's/^/    /' "${RENDERED_DIR}/gateway_app.py")
  ollama_adapter.py: |
$(sed 's/^/    /' "${RENDERED_DIR}/ollama_adapter.py")
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: direct-provider-sentinel-app
  namespace: ${PROVIDER_NAMESPACE}
data:
  provider_sentinel.py: |
$(sed 's/^/    /' "${RENDERED_DIR}/provider_sentinel.py")
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${GATEWAY_DEPLOYMENT}
  namespace: ${NAMESPACE}
  labels:
    dev-integration-profile: ${PROFILE_ID}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${GATEWAY_DEPLOYMENT}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${GATEWAY_DEPLOYMENT}
        governed-ai-gateway: "true"
    spec:
      containers:
        - name: gateway
          image: python:3.12-slim
          command: ["python", "/app/gateway_app.py"]
          env:
            - name: GOVERNED_AI_AUDIT_ROOT
              value: /var/lib/governed-ai-gateway
            - name: GOVERNED_AI_PROFILE_ID
              value: "${MODEL_PROFILE_ID}"
            - name: GOVERNED_AI_PROFILE_STATUS
              value: "${MODEL_PROFILE_STATUS}"
            - name: GOVERNED_AI_PROFILE_PURPOSE
              value: "${MODEL_PROFILE_PURPOSE}"
            - name: GOVERNED_AI_MODEL_ENVIRONMENT
              value: "${MODEL_ENVIRONMENT}"
            - name: GOVERNED_AI_BINDING_ID
              value: "${MODEL_BINDING_ID}"
            - name: GOVERNED_AI_BINDING_STATUS
              value: "${MODEL_BINDING_STATUS}"
            - name: GOVERNED_AI_BINDING_SELECTION_DIGEST
              value: "${MODEL_SELECTION_DIGEST}"
            - name: GOVERNED_AI_BINDING_SELECTION_REF
              value: "${MODEL_SELECTION_REF}"
            - name: GOVERNED_AI_PROFILE_REGISTRY_DIGEST
              value: "${MODEL_PROFILE_REGISTRY_DIGEST}"
            - name: GOVERNED_AI_ACCESS_PLANE_DIGEST
              value: "${MODEL_ACCESS_PLANE_DIGEST}"
            - name: GOVERNED_AI_FALLBACK_MODE
              value: "${MODEL_FALLBACK_MODE}"
            - name: GOVERNED_AI_MODEL_ACTIVATION_ELIGIBLE
              value: "${MODEL_ACTIVATION_ELIGIBLE}"
            - name: GOVERNED_AI_ACCESS_PLANE_ACTIVATION_ALLOWED
              value: "${ACCESS_PLANE_ACTIVATION_ALLOWED}"
            - name: GOVERNED_AI_UPSTREAM_PROVIDER
              value: "${UPSTREAM_PROVIDER}"
            - name: GOVERNED_AI_UPSTREAM_PROVIDER_ROUTE
              value: "${UPSTREAM_PROVIDER_ROUTE}"
            - name: GOVERNED_AI_PROVIDER_ROUTE_STATUS
              value: "${MODEL_PROVIDER_ROUTE_STATUS}"
            - name: GOVERNED_AI_UPSTREAM_MODEL
              value: "${UPSTREAM_MODEL}"
            - name: GOVERNED_AI_UPSTREAM_MODEL_DIGEST
              value: "${UPSTREAM_MODEL_DIGEST}"
            - name: GOVERNED_AI_PROVIDER_RUNTIME_VERSION
              value: "${PROVIDER_RUNTIME_VERSION}"
            - name: GOVERNED_AI_PROVIDER_BASE_URL
              value: "http://${provider_host_ip}:11434"
            - name: GOVERNED_AI_INVOCATION_PATH
              value: "${INVOCATION_PATH}"
            - name: GOVERNED_AI_OUTPUT_SCHEMA_REF
              value: "${PROVIDER_OUTPUT_SCHEMA_REF}"
            - name: GOVERNED_AI_ALLOWED_CALLERS
              value: "${ALLOWED_CALLERS_CSV}"
            - name: GOVERNED_AI_MAX_REQUEST_BYTES
              value: "16384"
            - name: GOVERNED_AI_PROVIDER_TIMEOUT_SECONDS
              value: "30"
            - name: GOVERNED_AI_PROVIDER_RETRY_COUNT
              value: "1"
            - name: GOVERNED_AI_PROVIDER_MAX_CONCURRENCY
              value: "2"
            - name: GOVERNED_AI_PROVIDER_MAX_OUTPUT_TOKENS
              value: "64"
          ports:
            - containerPort: 8080
              name: http
          readinessProbe:
            httpGet:
              path: /readyz
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          volumeMounts:
            - name: app
              mountPath: /app
              readOnly: true
            - name: audit
              mountPath: /var/lib/governed-ai-gateway
      volumes:
        - name: app
          configMap:
            name: ${GATEWAY_CONFIGMAP}
        - name: audit
          persistentVolumeClaim:
            claimName: ${GATEWAY_PVC}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: governed-ai-gateway-provider-egress
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      governed-ai-gateway: "true"
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: ${provider_host_ip}/32
      ports:
        - protocol: TCP
          port: 11434
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
---
apiVersion: v1
kind: Service
metadata:
  name: ${GATEWAY_SERVICE}
  namespace: ${NAMESPACE}
  labels:
    dev-integration-profile: ${PROFILE_ID}
spec:
  selector:
    app.kubernetes.io/name: ${GATEWAY_DEPLOYMENT}
  ports:
    - name: http
      port: 8080
      targetPort: http
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${PROVIDER_DEPLOYMENT}
  namespace: ${PROVIDER_NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${PROVIDER_DEPLOYMENT}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${PROVIDER_DEPLOYMENT}
        governed-ai-provider-sentinel: "true"
    spec:
      containers:
        - name: sentinel
          image: python:3.12-slim
          command: ["python", "/app/provider_sentinel.py"]
          ports:
            - containerPort: 8080
              name: http
          volumeMounts:
            - name: app
              mountPath: /app
              readOnly: true
      volumes:
        - name: app
          configMap:
            name: direct-provider-sentinel-app
---
apiVersion: v1
kind: Service
metadata:
  name: ${PROVIDER_SERVICE}
  namespace: ${PROVIDER_NAMESPACE}
spec:
  selector:
    app.kubernetes.io/name: ${PROVIDER_DEPLOYMENT}
  ports:
    - name: http
      port: 8080
      targetPort: http
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${CONSUMER_DEPLOYMENT}
  namespace: ${CONSUMER_NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${CONSUMER_DEPLOYMENT}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${CONSUMER_DEPLOYMENT}
        governed-ai-caller: "true"
    spec:
      containers:
        - name: probe
          image: python:3.12-slim
          command: ["sh", "-c", "sleep 365d"]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: governed-ai-consumer-default-deny-egress
  namespace: ${CONSUMER_NAMESPACE}
spec:
  podSelector:
    matchLabels:
      governed-ai-caller: "true"
  policyTypes:
    - Egress
  egress: []
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: governed-ai-consumer-allow-gateway-and-dns
  namespace: ${CONSUMER_NAMESPACE}
spec:
  podSelector:
    matchLabels:
      governed-ai-caller: "true"
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              governed-ai-gateway: "true"
          podSelector:
            matchLabels:
              governed-ai-gateway: "true"
      ports:
        - protocol: TCP
          port: 8080
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
EOF
}

run_consumer_probe() {
  local gateway_url="http://${GATEWAY_SERVICE}.${NAMESPACE}.svc.cluster.local:8080"
  local provider_url="http://${PROVIDER_SERVICE}.${PROVIDER_NAMESPACE}.svc.cluster.local:8080"
  kubectl_cmd -n "${CONSUMER_NAMESPACE}" exec -i "deployment/${CONSUMER_DEPLOYMENT}" -- \
    python - "${gateway_url}" "${provider_url}" "${PROVIDER_BASE_URL}" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

gateway_url = sys.argv[1]
provider_url = sys.argv[2]
ollama_url = sys.argv[3]

payload = {
    "profile_id": "intake-classifier-v1",
    "caller_identity": {
        "caller_id": "workspace-governance/intake-assist",
        "caller_repo": "workspace-governance",
        "caller_workflow": "governed-intake-assist",
        "decision_or_correlation_id": "devint-smoke-governed-ai-gateway",
        "requested_profile_id": "intake-classifier-v1",
    },
    "operator_identity": {
        "operator_id": "devint-operator",
    },
    "operator_acceptance_state": "not-recorded",
    "provider_output_schema_ref": "platform-engineering/security/schemas/intake-classification-result.schema.json",
    "input": {
        "operator_supplied_intake_notes": "Shared platform governance component smoke.",
    },
}

request = urllib.request.Request(
    f"{gateway_url}/v1/governed-ai/invoke",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

denied_payload = dict(payload)
denied_payload["provider_output_schema_ref"] = "invalid/schema.json"
denied_payload["caller_identity"] = {
    **payload["caller_identity"],
    "caller_id": "unapproved/consumer",
}
denied_request = urllib.request.Request(
    f"{gateway_url}/v1/governed-ai/invoke",
    data=json.dumps(denied_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(denied_request, timeout=10) as response:
        denied_status = response.status
        denied_body = json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    denied_status = exc.code
    denied_body = json.loads(exc.read().decode("utf-8"))

with urllib.request.urlopen(f"{gateway_url}/v1/audit/events/latest", timeout=10) as response:
    denied_audit = json.loads(response.read().decode("utf-8"))

try:
    with urllib.request.urlopen(request, timeout=60) as response:
        gateway_body = json.loads(response.read().decode("utf-8"))
        gateway_status = response.status
except urllib.error.HTTPError as exc:
    gateway_status = exc.code
    gateway_body = json.loads(exc.read().decode("utf-8"))

provider_direct_reachable = False
provider_error = None
try:
    with urllib.request.urlopen(f"{provider_url}/healthz", timeout=5) as response:
        provider_direct_reachable = response.status == 200
except Exception as exc:  # noqa: BLE001 - surfaced as smoke evidence, not hidden.
    provider_error = type(exc).__name__

ollama_direct_reachable = False
ollama_error = None
try:
    with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=5) as response:
        ollama_direct_reachable = response.status == 200
except Exception as exc:  # noqa: BLE001 - surfaced as smoke evidence, not hidden.
    ollama_error = type(exc).__name__

print(
    json.dumps(
        {
            "gateway_http_status": gateway_status,
            "gateway_policy_decision": gateway_body.get("policy_decision"),
            "gateway_suggested_decision": gateway_body.get("suggested_decision"),
            "gateway_confidence": gateway_body.get("confidence"),
            "gateway_reachable": gateway_status in {200, 403},
            "gateway_reasons": gateway_body.get("reasons", []),
            "unauthorized_http_status": denied_status,
            "unauthorized_policy_decision": denied_body.get("policy_decision"),
            "unauthorized_reasons": denied_body.get("reasons", []),
            "unauthorized_audit_selected_binding": (
                (denied_audit.get("latest") or {}).get("selected_binding")
            ),
            "gateway_binding_selection_ref": gateway_body.get("binding_selection_ref"),
            "direct_provider_reachable": provider_direct_reachable,
            "direct_provider_error": provider_error,
            "direct_ollama_reachable": ollama_direct_reachable,
            "direct_ollama_error": ollama_error,
        },
        indent=2,
        sort_keys=True,
    )
)
PY
}
