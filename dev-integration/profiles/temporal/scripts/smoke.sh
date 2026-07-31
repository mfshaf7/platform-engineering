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
  exit 2
fi

need_cmd k3s
need_cmd python3
wait_for_runtime_ready

cluster_health="$(
  kubectl_cmd -n "${NAMESPACE}" exec "deployment/temporal-admintools" -- \
    temporal operator cluster health 2>&1
)"
namespace_health="$(
  kubectl_cmd -n "${NAMESPACE}" exec "deployment/temporal-admintools" -- \
    temporal operator namespace describe --namespace "${TEMPORAL_WORKFLOW_NAMESPACE}" 2>&1
)"
pvc_phase="$(
  kubectl_cmd -n "${NAMESPACE}" get pvc \
    -l app.kubernetes.io/name=temporal-postgresql \
    -o jsonpath='{.items[0].status.phase}'
)"
policy_names="$(
  kubectl_cmd -n "${NAMESPACE}" get networkpolicy \
    -o jsonpath='{.items[*].metadata.name}'
)"

python3 - "${SMOKE_SUMMARY}" "${PROFILE_LIFECYCLE}" "${NAMESPACE}" \
  "${TEMPORAL_WORKFLOW_NAMESPACE}" "${pvc_phase}" "${policy_names}" \
  "${cluster_health}" "${namespace_health}" <<'PY'
import json
import pathlib
import sys

summary = {
    "profile": "temporal",
    "lifecycle": sys.argv[2],
    "kubernetes_namespace": sys.argv[3],
    "temporal_namespace": sys.argv[4],
    "persistence_claim_phase": sys.argv[5],
    "network_policies": sorted(sys.argv[6].split()),
    "cluster_healthy": "SERVING" in sys.argv[7].upper(),
    "namespace_describe_succeeded": bool(sys.argv[8].strip()),
    "smoke_mode": "read-only",
    "canonical_mutations_performed": 0,
}
required_policies = {
    "temporal-default-deny",
    "temporal-dns-egress",
    "temporal-server-mesh",
    "temporal-postgresql-access",
    "temporal-support-frontend",
    "temporal-support-egress",
    "temporal-schema-job-egress",
    "temporal-admitted-worker-egress",
    "temporal-admitted-worker-frontend",
}
failures = []
if summary["persistence_claim_phase"] != "Bound":
    failures.append("PostgreSQL persistence claim is not Bound")
missing_policies = sorted(required_policies - set(summary["network_policies"]))
if missing_policies:
    failures.append(f"Temporal network-policy set is incomplete: {missing_policies}")
if not summary["cluster_healthy"]:
    failures.append("Temporal cluster health did not report SERVING")
if not summary["namespace_describe_succeeded"]:
    failures.append("Temporal workflow namespace is unavailable")
summary["result"] = "passed" if not failures else "failed"
summary["failures"] = failures
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(path.read_text(encoding="utf-8"))
if failures:
    raise SystemExit(1)
PY
