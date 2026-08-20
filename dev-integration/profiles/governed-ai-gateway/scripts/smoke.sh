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
  "${UPSTREAM_MODEL}" <<'PY'
import json
import pathlib
import sys

probe = json.loads(sys.argv[1])
gateway = json.loads(sys.argv[2])
summary_path = pathlib.Path(sys.argv[3])
expected_provider = sys.argv[4]
expected_route = sys.argv[5]
expected_model = sys.argv[6]

latest = gateway["latest_audit"]["latest"] or {}
provider = gateway["provider_custody"]
ready = gateway["ready"]

summary = {
    "profile": "governed-ai-gateway",
    "runtime_ready": ready.get("ready") is True,
    "gateway_reachable_from_consumer": probe.get("gateway_reachable") is True,
    "gateway_policy_decision": probe.get("gateway_policy_decision"),
    "profile_status": ready.get("profile_status"),
    "access_plane_activation_allowed": ready.get("access_plane_activation_allowed"),
    "upstream_provider": ready.get("upstream_provider"),
    "provider_route": ready.get("provider_route"),
    "upstream_model": ready.get("upstream_model"),
    "audit_event_count": gateway["latest_audit"]["event_count"],
    "caller_identity_captured": bool((latest.get("caller_identity") or {}).get("caller_id")),
    "provider_secret_available": provider.get("provider_secret_available") is True,
    "provider_secret_projected_to_consumers": provider.get("provider_secret_projected_to_consumers") is True,
    "provider_token_projected": provider.get("token_value_projected") is True,
    "direct_provider_reachable_from_consumer": probe.get("direct_provider_reachable") is True,
    "direct_provider_error": probe.get("direct_provider_error"),
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
if not summary["provider_secret_available"]:
    failures.append("gateway provider secret is unavailable")
if summary["upstream_provider"] != expected_provider:
    failures.append("gateway upstream provider does not match the model registry")
if summary["provider_route"] != expected_route:
    failures.append("gateway provider route does not match the model registry")
if summary["upstream_model"] != expected_model:
    failures.append("gateway upstream model does not match the model registry")
if summary["access_plane_activation_allowed"] is not False:
    failures.append("gateway access plane unexpectedly allows profile activation")
if summary["provider_secret_projected_to_consumers"]:
    failures.append("provider secret is projected to consumers")
if summary["provider_token_projected"]:
    failures.append("provider token value was projected")
if summary["direct_provider_reachable_from_consumer"]:
    failures.append("consumer reached direct provider sentinel")

summary["result"] = "passed" if not failures else "failed"
summary["failures"] = failures

summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(summary_path.read_text(encoding="utf-8"))
if failures:
    raise SystemExit(1)
PY
