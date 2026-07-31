#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile "restore"
need_cmd k3s
need_cmd python3
need_cmd sha256sum
confirm_exact "${CONFIRM:-}" "restore-temporal" "Temporal restore"

backup_path="${DEVINT_BACKUP_FILE:-}"
if [[ -z "${backup_path}" || ! -f "${backup_path}" ]]; then
  printf 'refused: set DEVINT_BACKUP_FILE to an existing operator-local Temporal backup\n' >&2
  exit 2
fi

python3 - "${backup_path}" "${STATE_ROOT}" "${ARCHIVE_ROOT}" \
  "${NAMESPACE}" "${TEMPORAL_WORKFLOW_NAMESPACE}" <<'PY'
import hashlib
import json
import pathlib
import sys

backup = pathlib.Path(sys.argv[1]).resolve()
allowed_roots = [pathlib.Path(value).resolve() for value in sys.argv[2:4]]
if not any(root == backup or root in backup.parents for root in allowed_roots):
    raise SystemExit(
        "restore backup must stay under the operator's active state or reset archive"
    )

manifest_path = pathlib.Path(f"{backup}.manifest.json")
if not manifest_path.is_file():
    raise SystemExit(f"restore backup manifest is missing: {manifest_path}")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
actual_digest = hashlib.sha256(backup.read_bytes()).hexdigest()
if manifest.get("sha256") != actual_digest:
    raise SystemExit("restore backup digest does not match its manifest")
if pathlib.Path(manifest.get("backup_path", "")).resolve() != backup:
    raise SystemExit("restore backup path does not match its manifest")
if manifest.get("kubernetes_namespace") != sys.argv[4]:
    raise SystemExit("restore backup belongs to a different Kubernetes namespace")
if manifest.get("temporal_namespace") != sys.argv[5]:
    raise SystemExit("restore backup belongs to a different Temporal namespace")
if manifest.get("databases") != ["temporal", "temporal_visibility"]:
    raise SystemExit("restore backup does not contain the required database set")
if manifest.get("role_passwords_included") is not False:
    raise SystemExit("restore backup may contain PostgreSQL role passwords")
PY

initial_runtime_state="$(runtime_state)"
case "${initial_runtime_state}" in
  running)
    scale_temporal_deployments 0
    wait_for_temporal_deployments_suspended
    ;;
  suspended)
    kubectl_cmd -n "${NAMESPACE}" scale \
      "statefulset/${POSTGRESQL_STATEFULSET}" --replicas=1
    wait_for_postgresql
    ;;
  *)
    printf 'refused: Temporal restore requires a running or suspended runtime, got %s\n' \
      "${initial_runtime_state}" >&2
    exit 2
    ;;
esac

restore_failure_state() {
  if [[ "${initial_runtime_state}" == "suspended" ]]; then
    kubectl_cmd -n "${NAMESPACE}" scale \
      "statefulset/${POSTGRESQL_STATEFULSET}" --replicas=0 >/dev/null 2>&1 || true
    wait_for_zero_replicas "statefulset/${POSTGRESQL_STATEFULSET}" || true
  fi
}
trap restore_failure_state EXIT

pre_restore="${BACKUPS_DIR}/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).sql"
backup_database "${pre_restore}" >/dev/null

kubectl_cmd -n "${NAMESPACE}" exec -i "statefulset/${POSTGRESQL_STATEFULSET}" -- \
  sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres' \
  <"${backup_path}"

if [[ "${initial_runtime_state}" == "running" ]]; then
  scale_temporal_deployments 1
  wait_for_runtime_ready
else
  kubectl_cmd -n "${NAMESPACE}" scale \
    "statefulset/${POSTGRESQL_STATEFULSET}" --replicas=0
  wait_for_zero_replicas "statefulset/${POSTGRESQL_STATEFULSET}"
fi
trap - EXIT
write_status_file
final_runtime_state="$(runtime_state)"
if [[ "${final_runtime_state}" != "${initial_runtime_state}" ]]; then
  printf 'restore completed but runtime state did not return to %s; got %s\n' \
    "${initial_runtime_state}" "${final_runtime_state}" >&2
  exit 1
fi

python3 - "${STATE_ROOT}/restore-receipt.json" "${backup_path}" "${pre_restore}" \
  "${NAMESPACE}" "${initial_runtime_state}" "${final_runtime_state}" <<'PY'
from datetime import datetime, timezone
import json
import pathlib
import sys

payload = {
    "schema_version": 1,
    "action": "restore",
    "restored_from": str(pathlib.Path(sys.argv[2]).resolve()),
    "pre_restore_backup": str(pathlib.Path(sys.argv[3]).resolve()),
    "kubernetes_namespace": sys.argv[4],
    "runtime_state_before": sys.argv[5],
    "runtime_state_after": sys.argv[6],
    "completed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
printf 'Temporal restore completed from %s\n' "${backup_path}"
