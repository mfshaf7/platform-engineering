#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

if ! is_active_profile; then
  write_status_file
  cat >"${SMOKE_SUMMARY}" <<EOF
{
  "profile": "${PROFILE_ID}",
  "lifecycle": "${PROFILE_LIFECYCLE}",
  "runtime_launchable": false,
  "smoke_mode": "read-only",
  "result": "blocked-until-active-profile"
}
EOF
  cat "${SMOKE_SUMMARY}"
  exit 0
fi

need_cmd k3s
need_cmd python3

wait_for_runtime_ready

probe_json="$(run_consumer_probe)"

gateway_json="$(
  kubectl_cmd -n "${NAMESPACE}" exec -i "deployment/${GATEWAY_DEPLOYMENT}" -- python - <<'PY'
import json
import urllib.request

def get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:8080{path}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))

print(
    json.dumps(
        {
            "health": get("/healthz"),
            "ready": get("/readyz"),
            "provider_custody": get("/v1/provider/custody"),
            "latest_audit": get("/v1/audit/events/latest"),
        },
        sort_keys=True,
    )
)
PY
)"

python3 - \
  "${probe_json}" \
  "${gateway_json}" \
  "${SMOKE_SUMMARY}" \
  "${UPSTREAM_PROVIDER}" \
  "${UPSTREAM_PROVIDER_ROUTE}" \
  "${UPSTREAM_MODEL}" \
  "${UPSTREAM_MODEL_DIGEST}" \
  "${PROVIDER_RUNTIME_VERSION}" <<'PY'
import json
import pathlib
import sys

probe = json.loads(sys.argv[1])
gateway = json.loads(sys.argv[2])
summary_path = pathlib.Path(sys.argv[3])
expected_provider = sys.argv[4]
expected_route = sys.argv[5]
expected_model = sys.argv[6]
expected_digest = sys.argv[7]
expected_runtime_version = sys.argv[8]

latest = gateway["latest_audit"]["latest"] or {}
provider = gateway["provider_custody"]
ready = gateway["ready"]

summary = {
    "profile": "governed-ai-gateway",
    "runtime_ready": ready.get("ready") is True,
    "gateway_reachable_from_consumer": probe.get("gateway_reachable") is True,
    "gateway_policy_decision": probe.get("gateway_policy_decision"),
    "gateway_suggested_decision": probe.get("gateway_suggested_decision"),
    "gateway_confidence": probe.get("gateway_confidence"),
    "profile_status": ready.get("profile_status"),
    "access_plane_activation_allowed": ready.get("access_plane_activation_allowed"),
    "upstream_provider": ready.get("upstream_provider"),
    "provider_route": ready.get("provider_route"),
    "upstream_model": ready.get("upstream_model"),
    "upstream_model_digest": ready.get("upstream_model_digest"),
    "provider_runtime_version": ready.get("provider_runtime_version"),
    "audit_event_count": gateway["latest_audit"]["event_count"],
    "caller_identity_captured": bool((latest.get("caller_identity") or {}).get("caller_id")),
    "provider_credential_required": provider.get("provider_credential_required") is True,
    "provider_secret_available": provider.get("provider_secret_available") is True,
    "provider_secret_projected_to_consumers": provider.get("provider_secret_projected_to_consumers") is True,
    "provider_token_projected": provider.get("token_value_projected") is True,
    "direct_provider_reachable_from_consumer": probe.get("direct_provider_reachable") is True,
    "direct_provider_error": probe.get("direct_provider_error"),
    "direct_ollama_reachable_from_consumer": probe.get("direct_ollama_reachable") is True,
    "direct_ollama_error": probe.get("direct_ollama_error"),
    "provider_schema_valid": latest.get("provider_schema_valid") is True,
    "provider_latency_ms": latest.get("provider_latency_ms"),
    "provider_usage": latest.get("provider_usage"),
    "smoke_mode": "read-only",
}

failures = []
if not summary["runtime_ready"]:
    failures.append("gateway runtime is not ready")
if not summary["gateway_reachable_from_consumer"]:
    failures.append("consumer cannot reach governed gateway")
if summary["audit_event_count"] < 1:
    failures.append("gateway did not emit an audit event")
if not summary["caller_identity_captured"]:
    failures.append("caller identity was not captured in audit")
if summary["gateway_policy_decision"] != "allow":
    failures.append("gateway did not allow the governed invocation")
if summary["gateway_suggested_decision"] not in {"out-of-scope", "proposed", "admitted"}:
    failures.append("gateway did not return a valid suggested decision")
if summary["gateway_confidence"] not in {"low", "medium", "high"}:
    failures.append("gateway did not return a valid confidence")
if summary["provider_credential_required"]:
    failures.append("local Ollama route unexpectedly requires a provider credential")
if summary["provider_secret_available"]:
    failures.append("local Ollama route unexpectedly projects a provider secret")
if summary["upstream_provider"] != expected_provider:
    failures.append("gateway upstream provider does not match the model registry")
if summary["provider_route"] != expected_route:
    failures.append("gateway provider route does not match the model registry")
if summary["upstream_model"] != expected_model:
    failures.append("gateway upstream model does not match the model registry")
if summary["upstream_model_digest"] != expected_digest:
    failures.append("gateway model digest does not match the reviewed binding")
if summary["provider_runtime_version"] != expected_runtime_version:
    failures.append("gateway provider runtime version does not match the reviewed binding")
if summary["access_plane_activation_allowed"] is not True:
    failures.append("gateway access plane does not allow the reviewed dev-integration binding")
if summary["provider_secret_projected_to_consumers"]:
    failures.append("provider secret is projected to consumers")
if summary["provider_token_projected"]:
    failures.append("provider token value was projected")
if summary["direct_provider_reachable_from_consumer"]:
    failures.append("consumer reached direct provider sentinel")
if summary["direct_ollama_reachable_from_consumer"]:
    failures.append("consumer reached Ollama directly")
if not summary["provider_schema_valid"]:
    failures.append("gateway did not record valid provider schema evidence")

summary["result"] = "passed" if not failures else "failed"
summary["failures"] = failures

summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(summary_path.read_text(encoding="utf-8"))
if failures:
    raise SystemExit(1)
PY
