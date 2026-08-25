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
  "${MODEL_PROFILE_ID}" \
  "${MODEL_ENVIRONMENT}" \
  "${MODEL_BINDING_ID}" \
  "${MODEL_SELECTION_DIGEST}" \
  "${MODEL_SELECTION_REF}" \
  "${MODEL_FALLBACK_MODE}" \
  "${UPSTREAM_PROVIDER}" \
  "${UPSTREAM_PROVIDER_ROUTE}" \
  "${UPSTREAM_MODEL}" \
  "${UPSTREAM_MODEL_DIGEST}" \
  "${PROVIDER_RUNTIME_VERSION}" \
  "${WORK_DESIGN_SELECTION_JSON}" <<'PY'
import json
import pathlib
import sys

probe = json.loads(sys.argv[1])
gateway = json.loads(sys.argv[2])
summary_path = pathlib.Path(sys.argv[3])
expected_profile = sys.argv[4]
expected_environment = sys.argv[5]
expected_binding = sys.argv[6]
expected_selection_digest = sys.argv[7]
expected_selection_ref = sys.argv[8]
expected_fallback_mode = sys.argv[9]
expected_provider = sys.argv[10]
expected_route = sys.argv[11]
expected_model = sys.argv[12]
expected_digest = sys.argv[13]
expected_runtime_version = sys.argv[14]
expected_work_design = json.loads(sys.argv[15])

latest = probe.get("intake_audit") or {}
work_design_audit = probe.get("work_design_audit") or {}
work_design_denied_audit = probe.get("work_design_denied_audit") or {}
provider = gateway["provider_custody"]
ready = gateway["ready"]
ready_binding = ready.get("selected_binding") or {}
audit_binding = latest.get("selected_binding") or {}
denied_binding = probe.get("unauthorized_audit_selected_binding") or {}
work_design_binding = work_design_audit.get("selected_binding") or {}
work_design_denied_binding = work_design_denied_audit.get("selected_binding") or {}
work_design_output = probe.get("work_design_output") or {}
work_design_task = probe.get("work_design_task") or {}
expected_work_design_binding = {
    field: expected_work_design[field]
    for field in (
        "profile_id",
        "profile_status",
        "environment",
        "binding_id",
        "binding_status",
        "provider",
        "provider_route",
        "provider_route_status",
        "upstream_model",
        "profile_registry_digest",
        "access_plane_digest",
        "selection_digest",
        "selection_ref",
        "fallback_mode",
        "activation_eligible",
    )
}
expected_work_design_binding["upstream_model_digest"] = expected_work_design["model_digest"]
expected_work_design_binding["provider_runtime_version"] = expected_work_design["runtime_version"]

summary = {
    "profile": "governed-ai-gateway",
    "runtime_ready": ready.get("ready") is True,
    "gateway_reachable_from_consumer": probe.get("gateway_reachable") is True,
    "gateway_policy_decision": probe.get("gateway_policy_decision"),
    "gateway_suggested_decision": probe.get("gateway_suggested_decision"),
    "gateway_confidence": probe.get("gateway_confidence"),
    "unauthorized_http_status": probe.get("unauthorized_http_status"),
    "unauthorized_policy_decision": probe.get("unauthorized_policy_decision"),
    "unauthorized_reasons": probe.get("unauthorized_reasons", []),
    "profile_status": ready.get("profile_status"),
    "access_plane_activation_allowed": ready.get("access_plane_activation_allowed"),
    "upstream_provider": ready.get("upstream_provider"),
    "provider_route": ready.get("provider_route"),
    "upstream_model": ready.get("upstream_model"),
    "upstream_model_digest": ready.get("upstream_model_digest"),
    "provider_runtime_version": ready.get("provider_runtime_version"),
    "binding_selection_ref": probe.get("gateway_binding_selection_ref"),
    "selected_binding": ready_binding,
    "audit_selected_binding": audit_binding,
    "unauthorized_audit_selected_binding": denied_binding,
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
    "ready_profile_ids": ready.get("ready_profile_ids", []),
    "work_design_http_status": probe.get("work_design_http_status"),
    "work_design_policy_decision": probe.get("work_design_policy_decision"),
    "work_design_task": work_design_task,
    "work_design_output": work_design_output,
    "work_design_binding_selection_ref": probe.get("work_design_binding_selection_ref"),
    "work_design_selected_binding": work_design_binding,
    "work_design_audit_caller": (work_design_audit.get("caller_identity") or {}).get("caller_id"),
    "work_design_audit_task_kind": work_design_audit.get("task_kind"),
    "work_design_audit_packet_ref": work_design_audit.get("model_safe_packet_ref"),
    "work_design_provider_schema_valid": work_design_audit.get("provider_schema_valid") is True,
    "work_design_denied_http_status": probe.get("work_design_denied_http_status"),
    "work_design_denied_policy_decision": probe.get("work_design_denied_policy_decision"),
    "work_design_denied_reasons": probe.get("work_design_denied_reasons", []),
    "work_design_denied_selected_binding": work_design_denied_binding,
    "smoke_mode": "read-only",
}

failures = []
if not summary["runtime_ready"]:
    failures.append("gateway runtime is not ready")
if not summary["gateway_reachable_from_consumer"]:
    failures.append("consumer cannot reach governed gateway")
if summary["audit_event_count"] < 4:
    failures.append("gateway did not retain the complete intake and Work Design probe trail")
if not summary["caller_identity_captured"]:
    failures.append("caller identity was not captured in audit")
if summary["gateway_policy_decision"] != "allow":
    failures.append("gateway did not allow the governed invocation")
if summary["gateway_suggested_decision"] not in {"out-of-scope", "proposed", "admitted"}:
    failures.append("gateway did not return a valid suggested decision")
if summary["gateway_confidence"] not in {"low", "medium", "high"}:
    failures.append("gateway did not return a valid confidence")
if summary["unauthorized_http_status"] != 403 or summary["unauthorized_policy_decision"] != "deny":
    failures.append("gateway did not deny the unauthorized/schema-mismatched invocation")
if "output-schema-mismatch" not in summary["unauthorized_reasons"]:
    failures.append("gateway denial did not identify the output schema mismatch")
if "caller-not-allowed" not in summary["unauthorized_reasons"]:
    failures.append("gateway denial did not identify the unauthorized caller")
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
if ready_binding.get("profile_id") != expected_profile:
    failures.append("gateway selected-binding profile does not match the resolved profile")
if ready_binding.get("environment") != expected_environment:
    failures.append("gateway selected-binding environment does not match the resolved environment")
if ready_binding.get("binding_id") != expected_binding:
    failures.append("gateway selected-binding id does not match the resolved binding")
if ready_binding.get("selection_digest") != expected_selection_digest:
    failures.append("gateway selected-binding digest does not match resolver evidence")
if ready_binding.get("selection_ref") != expected_selection_ref:
    failures.append("gateway selected-binding ref does not match resolver evidence")
if ready_binding.get("fallback_mode") != expected_fallback_mode:
    failures.append("gateway fallback posture does not match resolver evidence")
if summary["binding_selection_ref"] != expected_selection_ref:
    failures.append("gateway invocation response does not bind the selected runtime")
if audit_binding != ready_binding:
    failures.append("allowed invocation audit does not bind readiness selection evidence")
if denied_binding != ready_binding:
    failures.append("denied invocation audit does not bind readiness selection evidence")
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
if set(summary["ready_profile_ids"]) != {
    "intake-classifier-v1",
    "delivery-work-design-advisor-v1",
}:
    failures.append("gateway readiness does not expose both independently active profiles")
if summary["work_design_http_status"] != 200:
    failures.append("Work Design invocation did not complete successfully")
if summary["work_design_policy_decision"] != "allow":
    failures.append("gateway did not allow the reviewed Work Design caller")
if summary["work_design_task"] != {
    "kind": "context_advice",
    "contract_ref": "oos.delivery-work-design.v1",
    "version": "1.0",
}:
    failures.append("Work Design response did not preserve the exact typed task identity")
if set(work_design_output) != {
    "confidence",
    "required_operator_action",
    "text",
    "affected_node_id",
    "patch_proposal",
}:
    failures.append("Work Design response did not match the strict output shape")
if summary["work_design_binding_selection_ref"] != expected_work_design["selection_ref"]:
    failures.append("Work Design response did not bind the reviewed runtime selection")
if summary["work_design_selected_binding"] != expected_work_design_binding:
    failures.append("Work Design audit did not bind the reviewed runtime selection")
if summary["work_design_audit_caller"] != "operator-orchestration-service/work-design-assist":
    failures.append("Work Design audit did not retain the exact caller identity")
if summary["work_design_audit_task_kind"] != "context_advice":
    failures.append("Work Design audit did not retain the exact task kind")
if summary["work_design_audit_packet_ref"] != "cgg://packets/devint-work-design-smoke":
    failures.append("Work Design audit did not retain the model-safe packet reference")
if not summary["work_design_provider_schema_valid"]:
    failures.append("Work Design provider output did not pass strict schema validation")
if (
    summary["work_design_denied_http_status"] != 403
    or summary["work_design_denied_policy_decision"] != "deny"
):
    failures.append("gateway did not deny the mismatched Work Design request")
for reason in ("caller-not-allowed", "profile-identity-mismatch", "task-kind-not-allowed"):
    if reason not in summary["work_design_denied_reasons"]:
        failures.append(f"Work Design denial did not identify {reason}")
if summary["work_design_denied_selected_binding"] != expected_work_design_binding:
    failures.append("denied Work Design audit did not bind the reviewed runtime selection")

summary["result"] = "passed" if not failures else "failed"
summary["failures"] = failures

summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(summary_path.read_text(encoding="utf-8"))
if failures:
    raise SystemExit(1)
PY
