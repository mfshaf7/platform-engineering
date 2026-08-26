#!/usr/bin/env bash
set -euo pipefail

readonly PROFILE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly OWNER_REPO_ROOT="$(cd "${PROFILE_ROOT}/../../.." && pwd)"
readonly PROFILE_ID="${DEVINT_PROFILE_ID:-governed-ai-gateway}"
readonly OPERATOR="${DEVINT_OPERATOR:-${USER:-operator}}"
readonly NAMESPACE="${DEVINT_NAMESPACE:-devint-${PROFILE_ID}-${OPERATOR}}"
readonly CONSUMER_NAMESPACE="${DEVINT_GAI_CONSUMER_NAMESPACE:-${NAMESPACE}-consumer}"
readonly PROVIDER_NAMESPACE="${DEVINT_GAI_PROVIDER_NAMESPACE:-${NAMESPACE}-provider-sentinel}"
readonly TRUSTED_CONSUMER_NAMESPACE="${DEVINT_GAI_TRUSTED_CONSUMER_NAMESPACE:-devint-no-external-consumer-admitted}"
readonly STATE_ROOT="${DEVINT_STATE_ROOT:-${OWNER_REPO_ROOT}/.dev-integration/${PROFILE_ID}/${OPERATOR}}"
readonly SESSION_FILE="${DEVINT_SESSION_FILE:-${STATE_ROOT}/session.yaml}"
readonly PROMOTION_REPORT="${DEVINT_PROMOTION_REPORT:-${STATE_ROOT}/promotion-report.yaml}"
readonly DEVINT_KUBECONFIG_PATH="${DEVINT_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

export KUBECONFIG="${DEVINT_KUBECONFIG_PATH}"

read -r -a KUBECTL_CMD <<<"${DEVINT_KUBECTL:-k3s kubectl}"

readonly STATUS_FILE="${STATE_ROOT}/profile-status.txt"
readonly SMOKE_SUMMARY="${STATE_ROOT}/smoke-summary.json"
readonly MODEL_SELECTION_RECEIPT="${STATE_ROOT}/model-binding-selection.json"
readonly MODEL_SELECTIONS_RECEIPT="${STATE_ROOT}/model-profile-selections.json"
readonly PROFILE_PROMOTION_NOTES="${STATE_ROOT}/profile-promotion-notes.md"
readonly RENDERED_DIR="${STATE_ROOT}/rendered"
readonly LOGS_DIR="${STATE_ROOT}/logs"
readonly ACCESS_LOCAL_PORT="${DEVINT_GAI_GATEWAY_LOCAL_PORT:-18290}"
readonly RUNTIME_SOURCE_DIR="${PROFILE_ROOT}/runtime"
readonly COMPATIBILITY_MODEL_PROFILE_ID="intake-classifier-v1"
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

load_model_profile_selections() {
  python3 "${RUNTIME_SOURCE_DIR}/model_profile_resolver.py" \
    --profile-registry "${OWNER_REPO_ROOT}/security/governed-ai-model-profiles.yaml" \
    --access-plane "${OWNER_REPO_ROOT}/security/governed-ai-access-plane.yaml" \
    --all \
    --environment "${MODEL_ENVIRONMENT_REQUESTED}"
}

MODEL_SELECTIONS_JSON="$(load_model_profile_selections)"
readonly MODEL_SELECTIONS_JSON
MODEL_SELECTION_JSON="$({
  python3 -c '
import json
import sys

registry = json.load(sys.stdin)
profile_id = sys.argv[1]
try:
    profile = registry["profiles"][profile_id]
except KeyError as exc:
    raise SystemExit(f"compatibility profile {profile_id!r} is not resolved") from exc
print(json.dumps(profile, indent=2, sort_keys=True))
' "${COMPATIBILITY_MODEL_PROFILE_ID}" <<<"${MODEL_SELECTIONS_JSON}"
})"
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
readonly MODEL_SMOKE_CALLER_ID="${ALLOWED_CALLERS_CSV%%,*}"
readonly WORK_DESIGN_MODEL_PROFILE_ID="delivery-work-design-advisor-v1"
WORK_DESIGN_SELECTION_JSON="$({
  python3 -c '
import json
import sys

registry = json.load(sys.stdin)
profile_id = sys.argv[1]
try:
    profile = registry["profiles"][profile_id]
except KeyError as exc:
    raise SystemExit(f"Work Design profile {profile_id!r} is not resolved") from exc
print(json.dumps(profile, sort_keys=True))
' "${WORK_DESIGN_MODEL_PROFILE_ID}" <<<"${MODEL_SELECTIONS_JSON}"
})"
readonly WORK_DESIGN_SELECTION_JSON
mapfile -t WORK_DESIGN_PROBE_CONTRACT < <(
  python3 -c '
import json
import sys

selection = json.load(sys.stdin)
task = selection["task_contracts"]["context_advice"]
print(selection["allowed_callers"][0])
print(task["task_kind"])
print(task["contract_ref"])
print(task["contract_version"])
print(task["provider_output_schema_ref"])
' <<<"${WORK_DESIGN_SELECTION_JSON}"
)
if [[ "${#WORK_DESIGN_PROBE_CONTRACT[@]}" -ne 5 ]]; then
  echo "Unable to resolve Work Design probe contract" >&2
  exit 1
fi
readonly WORK_DESIGN_SMOKE_CALLER_ID="${WORK_DESIGN_PROBE_CONTRACT[0]}"
readonly WORK_DESIGN_TASK_KIND="${WORK_DESIGN_PROBE_CONTRACT[1]}"
readonly WORK_DESIGN_TASK_CONTRACT_REF="${WORK_DESIGN_PROBE_CONTRACT[2]}"
readonly WORK_DESIGN_TASK_CONTRACT_VERSION="${WORK_DESIGN_PROBE_CONTRACT[3]}"
readonly WORK_DESIGN_OUTPUT_SCHEMA_REF="${WORK_DESIGN_PROBE_CONTRACT[4]}"

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
trusted composition consumer namespace: ${TRUSTED_CONSUMER_NAMESPACE}
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
  printf '%s\n' "${MODEL_SELECTIONS_JSON}" >"${MODEL_SELECTIONS_RECEIPT}"
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
  local runtime_file
  for runtime_file in \
    gateway_app.py \
    gateway_policy.py \
    ollama_adapter.py \
    strict_output_schema.py; do
    cp "${RUNTIME_SOURCE_DIR}/${runtime_file}" "${RENDERED_DIR}/${runtime_file}"
  done
  cp "${MODEL_SELECTIONS_RECEIPT}" "${RENDERED_DIR}/model-profile-selections.json"
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
  gateway_policy.py: |
$(sed 's/^/    /' "${RENDERED_DIR}/gateway_policy.py")
  ollama_adapter.py: |
$(sed 's/^/    /' "${RENDERED_DIR}/ollama_adapter.py")
  strict_output_schema.py: |
$(sed 's/^/    /' "${RENDERED_DIR}/strict_output_schema.py")
  model-profile-selections.json: |
$(sed 's/^/    /' "${RENDERED_DIR}/model-profile-selections.json")
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
            - name: GOVERNED_AI_PROFILE_SELECTIONS_PATH
              value: /app/model-profile-selections.json
            - name: GOVERNED_AI_COMPATIBILITY_PROFILE_ID
              value: "${COMPATIBILITY_MODEL_PROFILE_ID}"
            - name: GOVERNED_AI_OLLAMA_BASE_URL
              value: "http://${provider_host_ip}:11434"
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
  name: governed-ai-gateway-default-deny-ingress
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      governed-ai-gateway: "true"
  policyTypes:
    - Ingress
  ingress: []
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: governed-ai-gateway-admitted-callers
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      governed-ai-gateway: "true"
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ${CONSUMER_NAMESPACE}
          podSelector:
            matchLabels:
              governed-ai-caller: "true"
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ${TRUSTED_CONSUMER_NAMESPACE}
          podSelector:
            matchLabels:
              app.kubernetes.io/name: operator-orchestration-service
      ports:
        - protocol: TCP
          port: 8080
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
    python - "${gateway_url}" "${provider_url}" "${PROVIDER_BASE_URL}" \
      "${MODEL_PROFILE_ID}" "${MODEL_SMOKE_CALLER_ID}" \
      "${PROVIDER_OUTPUT_SCHEMA_REF}" \
      "${WORK_DESIGN_MODEL_PROFILE_ID}" "${WORK_DESIGN_SMOKE_CALLER_ID}" \
      "${WORK_DESIGN_TASK_KIND}" "${WORK_DESIGN_TASK_CONTRACT_REF}" \
      "${WORK_DESIGN_TASK_CONTRACT_VERSION}" \
      "${WORK_DESIGN_OUTPUT_SCHEMA_REF}" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

gateway_url = sys.argv[1]
provider_url = sys.argv[2]
ollama_url = sys.argv[3]
profile_id = sys.argv[4]
caller_id = sys.argv[5]
output_schema_ref = sys.argv[6]
caller_repo, caller_workflow = caller_id.split("/", 1)
work_design_profile_id = sys.argv[7]
work_design_caller_id = sys.argv[8]
work_design_task_kind = sys.argv[9]
work_design_contract_ref = sys.argv[10]
work_design_contract_version = sys.argv[11]
work_design_schema_ref = sys.argv[12]
work_design_caller_repo, work_design_caller_workflow = work_design_caller_id.split("/", 1)


def invoke(payload):
    request = urllib.request.Request(
        f"{gateway_url}/v1/governed-ai/invoke",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def latest_audit():
    with urllib.request.urlopen(f"{gateway_url}/v1/audit/events/latest", timeout=10) as response:
        return json.loads(response.read().decode("utf-8")).get("latest") or {}

payload = {
    "profile_id": profile_id,
    "caller_identity": {
        "caller_id": caller_id,
        "caller_repo": caller_repo,
        "caller_workflow": caller_workflow,
        "decision_or_correlation_id": "devint-smoke-governed-ai-gateway",
        "requested_profile_id": profile_id,
    },
    "operator_identity": {
        "operator_id": "devint-operator",
    },
    "operator_acceptance_state": "not-recorded",
    "provider_output_schema_ref": output_schema_ref,
    "input": {
        "operator_supplied_intake_notes": "Shared platform governance component smoke.",
    },
}

denied_payload = dict(payload)
denied_payload["provider_output_schema_ref"] = "invalid/schema.json"
denied_payload["caller_identity"] = {
    **payload["caller_identity"],
    "caller_id": "unapproved/consumer",
}
denied_status, denied_body = invoke(denied_payload)
denied_audit = latest_audit()
gateway_status, gateway_body = invoke(payload)
intake_audit = latest_audit()

work_design_payload = {
    "profile_id": work_design_profile_id,
    "caller_identity": {
        "caller_id": work_design_caller_id,
        "caller_repo": work_design_caller_repo,
        "caller_workflow": work_design_caller_workflow,
        "decision_or_correlation_id": "devint-smoke-work-design",
        "requested_profile_id": work_design_profile_id,
    },
    "operator_identity": {"operator_id": "devint-operator"},
    "operator_acceptance_state": "not-recorded",
    "task": {
        "kind": work_design_task_kind,
        "contract_ref": work_design_contract_ref,
        "version": work_design_contract_version,
    },
    "provider_output_schema_ref": work_design_schema_ref,
    "input": {
        "task_instruction": (
            "Review the supplied Work Design context. Return advice only and do not "
            "claim to mutate canonical state."
        ),
        "operator_prompt": "Identify one useful next review action for this package.",
        "model_safe_packet": {
            "packet_ref": "cgg://packets/devint-work-design-smoke",
            "redaction_receipt_ref": "cgg://receipts/devint-work-design-redaction",
            "projection_receipt_ref": "cgg://receipts/devint-work-design-projection",
            "content": (
                "Synthetic Work Design package. The package has a bounded context "
                "brief and requires operator review before any apply action."
            ),
        },
    },
}
work_design_denied_payload = json.loads(json.dumps(work_design_payload))
work_design_denied_payload["caller_identity"]["caller_id"] = "unapproved/consumer"
work_design_denied_payload["caller_identity"]["requested_profile_id"] = profile_id
work_design_denied_payload["task"]["kind"] = "unapproved_task"
work_design_denied_status, work_design_denied_body = invoke(work_design_denied_payload)
work_design_denied_audit = latest_audit()
work_design_status, work_design_body = invoke(work_design_payload)
work_design_audit = latest_audit()

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
                denied_audit.get("selected_binding")
            ),
            "intake_audit": intake_audit,
            "gateway_binding_selection_ref": gateway_body.get("binding_selection_ref"),
            "work_design_http_status": work_design_status,
            "work_design_policy_decision": work_design_body.get("policy_decision"),
            "work_design_task": work_design_body.get("task"),
            "work_design_output": work_design_body.get("output"),
            "work_design_binding_selection_ref": work_design_body.get("binding_selection_ref"),
            "work_design_audit": work_design_audit,
            "work_design_denied_http_status": work_design_denied_status,
            "work_design_denied_policy_decision": work_design_denied_body.get("policy_decision"),
            "work_design_denied_reasons": work_design_denied_body.get("reasons", []),
            "work_design_denied_audit": work_design_denied_audit,
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
