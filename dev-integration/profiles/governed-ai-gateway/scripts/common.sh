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
readonly PROFILE_PROMOTION_NOTES="${STATE_ROOT}/profile-promotion-notes.md"
readonly RENDERED_DIR="${STATE_ROOT}/rendered"
readonly LOGS_DIR="${STATE_ROOT}/logs"
readonly LOCAL_SECRETS_ENV="${STATE_ROOT}/local-secrets.env"
readonly ACCESS_LOCAL_PORT="${DEVINT_GAI_GATEWAY_LOCAL_PORT:-18290}"

readonly GATEWAY_DEPLOYMENT="governed-ai-gateway"
readonly GATEWAY_SERVICE="governed-ai-gateway"
readonly GATEWAY_PVC="governed-ai-gateway-audit"
readonly GATEWAY_SECRET="governed-ai-gateway-provider"
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

generate_random_hex() {
  python3 - <<'PY'
import secrets
print(secrets.token_hex(24))
PY
}

ensure_local_secrets() {
  ensure_state_dirs
  if [[ -f "${LOCAL_SECRETS_ENV}" ]]; then
    return
  fi

  cat >"${LOCAL_SECRETS_ENV}" <<EOF
GOVERNED_AI_PROVIDER_TOKEN=$(generate_random_hex)
EOF
}

load_local_secrets() {
  # shellcheck disable=SC1090
  source "${LOCAL_SECRETS_ENV}"
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

is_active_profile() {
  [[ "${PROFILE_LIFECYCLE}" == "active" ]]
}

write_status_file() {
  ensure_state_dirs
  cat >"${STATUS_FILE}" <<EOF
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
profile status input: ${GOVERNED_AI_PROFILE_STATUS:-suspended}
EOF
}

print_status() {
  write_status_file
  cat "${STATUS_FILE}"
}

fail_not_active() {
  print_status
  echo
  echo "refused: ${PROFILE_ID} is ${PROFILE_LIFECYCLE}, not active; governed AI gateway runtime launch is intentionally blocked." >&2
  exit 2
}

require_active_profile() {
  if ! is_active_profile; then
    fail_not_active
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

AUDIT_ROOT = Path(os.environ.get("GOVERNED_AI_AUDIT_ROOT", "/var/lib/governed-ai-gateway"))
AUDIT_LEDGER = AUDIT_ROOT / "audit-ledger.jsonl"
PROFILE_ID = os.environ.get("GOVERNED_AI_PROFILE_ID", "intake-classifier-v1")
PROFILE_STATUS = os.environ.get("GOVERNED_AI_PROFILE_STATUS", "suspended")
UPSTREAM_MODEL = os.environ.get("GOVERNED_AI_UPSTREAM_MODEL", "pending-selection")
INVOCATION_PATH = os.environ.get("GOVERNED_AI_INVOCATION_PATH", "governed-ai-gateway")
OUTPUT_SCHEMA_REF = os.environ.get(
    "GOVERNED_AI_OUTPUT_SCHEMA_REF",
    "workspace-governance/contracts/schemas/intake-ai-suggestion.schema.json",
)
PROVIDER_SECRET_REF = os.environ.get(
    "GOVERNED_AI_PROVIDER_SECRET_REF",
    "secret/governed-ai-gateway-provider/token",
)
PROVIDER_TOKEN = os.environ.get("GOVERNED_AI_PROVIDER_TOKEN", "")

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


def classify_intake_note(note: str) -> tuple[str, str]:
    lowered = note.lower()
    if "secret" in lowered or "credential" in lowered or "privileged" in lowered:
        return "proposed", "medium"
    if "out-of-scope" in lowered or "archive" in lowered:
        return "out-of-scope", "medium"
    if "shared" in lowered or "platform" in lowered or "governance" in lowered:
        return "admitted", "medium"
    return "proposed", "low"


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
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.send_json(200, {"status": "ok", "component": "governed-ai-gateway"})
            return
        if self.path == "/readyz":
            self.send_json(
                200,
                {
                    "ready": True,
                    "profile_id": PROFILE_ID,
                    "profile_status": PROFILE_STATUS,
                    "provider_custody": bool(PROVIDER_TOKEN),
                    "raw_provider_token_projected": False,
                },
            )
            return
        if self.path == "/v1/provider/custody":
            self.send_json(
                200,
                {
                    "provider_secret_available": bool(PROVIDER_TOKEN),
                    "provider_secret_ref": PROVIDER_SECRET_REF,
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

        request = self.read_json()
        caller_identity = request.get("caller_identity") or {}
        missing = [field for field in REQUIRED_CALLER_FIELDS if not caller_identity.get(field)]
        requested_profile = request.get("profile_id") or caller_identity.get("requested_profile_id")
        output_schema_ref = request.get("output_schema_ref")
        operator_identity = request.get("operator_identity") or {}
        operator_acceptance_state = request.get("operator_acceptance_state", "not-recorded")

        denial_reasons: list[str] = []
        if missing:
            denial_reasons.append("missing-caller-identity:" + ",".join(missing))
        if requested_profile != PROFILE_ID:
            denial_reasons.append("profile-not-allowed")
        if PROFILE_STATUS != "active":
            denial_reasons.append("profile-not-active")
        if UPSTREAM_MODEL == "pending-selection":
            denial_reasons.append("upstream-model-pending-selection")
        if output_schema_ref != OUTPUT_SCHEMA_REF:
            denial_reasons.append("output-schema-mismatch")
        if not operator_identity.get("operator_id"):
            denial_reasons.append("operator-identity-missing")

        policy_decision = "deny" if denial_reasons else "allow"
        note = str((request.get("input") or {}).get("operator_supplied_intake_notes", ""))
        suggested_decision, confidence = classify_intake_note(note)
        correlation_id = caller_identity.get("decision_or_correlation_id") or request.get("correlation_id")

        event = append_audit(
            {
                "correlation_id": correlation_id,
                "caller_identity": caller_identity,
                "operator_identity": operator_identity,
                "approved_profile_id": PROFILE_ID,
                "requested_profile_id": requested_profile,
                "invocation_path": INVOCATION_PATH,
                "purpose": "workspace-intake-assist",
                "output_schema_ref": OUTPUT_SCHEMA_REF,
                "policy_decision": policy_decision,
                "policy_reasons": denial_reasons,
                "outcome": "denied" if denial_reasons else "suggestion-produced",
                "operator_acceptance_state": operator_acceptance_state,
                "override_reason": request.get("override_reason"),
                "provider_secret_ref": PROVIDER_SECRET_REF,
                "provider_secret_projected": False,
            }
        )

        if denial_reasons:
            self.send_json(
                403,
                {
                    "policy_decision": "deny",
                    "reasons": denial_reasons,
                    "audit_ref": f"local-ledger:{event['event_digest']}",
                },
            )
            return

        self.send_json(
            200,
            {
                "profile_id": PROFILE_ID,
                "policy_status": PROFILE_STATUS,
                "decision_id": correlation_id,
                "generated_at": event["event_time"],
                "confidence": confidence,
                "caller_id": caller_identity.get("caller_id"),
                "invocation_path": INVOCATION_PATH,
                "suggested_decision": suggested_decision,
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
  ensure_local_secrets
  load_local_secrets
  render_gateway_app
  render_provider_sentinel_app

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
kind: Secret
metadata:
  name: ${GATEWAY_SECRET}
  namespace: ${NAMESPACE}
  labels:
    dev-integration-profile: ${PROFILE_ID}
type: Opaque
stringData:
  GOVERNED_AI_PROVIDER_TOKEN: "${GOVERNED_AI_PROVIDER_TOKEN}"
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
              value: intake-classifier-v1
            - name: GOVERNED_AI_PROFILE_STATUS
              value: "${GOVERNED_AI_PROFILE_STATUS:-suspended}"
            - name: GOVERNED_AI_UPSTREAM_MODEL
              value: "${GOVERNED_AI_UPSTREAM_MODEL:-pending-selection}"
            - name: GOVERNED_AI_INVOCATION_PATH
              value: governed-ai-gateway
            - name: GOVERNED_AI_OUTPUT_SCHEMA_REF
              value: workspace-governance/contracts/schemas/intake-ai-suggestion.schema.json
            - name: GOVERNED_AI_PROVIDER_SECRET_REF
              value: secret/governed-ai-gateway-provider/token
          envFrom:
            - secretRef:
                name: ${GATEWAY_SECRET}
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
    python - "${gateway_url}" "${provider_url}" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

gateway_url = sys.argv[1]
provider_url = sys.argv[2]

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
    "output_schema_ref": "workspace-governance/contracts/schemas/intake-ai-suggestion.schema.json",
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

try:
    with urllib.request.urlopen(request, timeout=10) as response:
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

print(
    json.dumps(
        {
            "gateway_http_status": gateway_status,
            "gateway_policy_decision": gateway_body.get("policy_decision"),
            "gateway_reachable": gateway_status in {200, 403},
            "gateway_reasons": gateway_body.get("reasons", []),
            "direct_provider_reachable": provider_direct_reachable,
            "direct_provider_error": provider_error,
        },
        indent=2,
        sort_keys=True,
    )
)
PY
}
