#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile "reset"
need_cmd k3s
need_cmd python3
need_cmd sha256sum
confirm_exact "${CONFIRM:-}" "reset-temporal" "Temporal reset"
assert_state_root_boundary

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive_dir="${ARCHIVE_ROOT}/${timestamp}"
mkdir -p "${archive_dir}"

if kubectl_cmd -n "${NAMESPACE}" get "statefulset/${POSTGRESQL_STATEFULSET}" \
  >/dev/null 2>&1; then
  scale_temporal_deployments 0
  wait_for_temporal_deployments_suspended
  original_replicas="$(
    kubectl_cmd -n "${NAMESPACE}" get "statefulset/${POSTGRESQL_STATEFULSET}" \
      -o jsonpath='{.spec.replicas}'
  )"
  if [[ "${original_replicas}" == "0" ]]; then
    kubectl_cmd -n "${NAMESPACE}" scale \
      "statefulset/${POSTGRESQL_STATEFULSET}" --replicas=1
    wait_for_postgresql
  fi
  backup_path="$(backup_database "${archive_dir}/pre-reset.sql")"
  cp "${backup_path}.manifest.json" "${archive_dir}/pre-reset.manifest.json"
fi

for evidence in \
  "${SESSION_FILE}" \
  "${STATUS_FILE}" \
  "${SMOKE_SUMMARY}" \
  "${PROFILE_PROMOTION_NOTES}" \
  "${PROMOTION_REPORT}"; do
  if [[ -f "${evidence}" ]]; then
    cp "${evidence}" "${archive_dir}/"
  fi
done

kubectl_cmd delete namespace "${NAMESPACE}" --ignore-not-found=true
rm -rf "${STATE_ROOT}"

python3 - "${archive_dir}/reset-receipt.json" "${NAMESPACE}" "${timestamp}" <<'PY'
import json
import pathlib
import sys

payload = {
    "schema_version": 1,
    "action": "reset",
    "kubernetes_namespace": sys.argv[2],
    "completed_at": sys.argv[3],
    "runtime_namespace_removed": True,
    "pre_reset_backup_preserved": (pathlib.Path(sys.argv[1]).parent / "pre-reset.sql").exists(),
}
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
printf 'Temporal dev-integration runtime reset; pre-reset evidence preserved at %s\n' \
  "${archive_dir}"
