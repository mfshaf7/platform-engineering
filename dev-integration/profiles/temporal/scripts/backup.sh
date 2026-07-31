#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile "backup"
need_cmd k3s
need_cmd sha256sum

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
    printf 'refused: Temporal backup requires a running or suspended runtime, got %s\n' \
      "${initial_runtime_state}" >&2
    exit 2
    ;;
esac

restore_initial_runtime_state() {
  if [[ "${initial_runtime_state}" == "running" ]]; then
    scale_temporal_deployments 1
    wait_for_runtime_ready
  else
    kubectl_cmd -n "${NAMESPACE}" scale \
      "statefulset/${POSTGRESQL_STATEFULSET}" --replicas=0 >/dev/null 2>&1 || true
    wait_for_zero_replicas "statefulset/${POSTGRESQL_STATEFULSET}"
  fi
}
trap 'restore_initial_runtime_state || true' EXIT

backup_path="${DEVINT_BACKUP_FILE:-${BACKUPS_DIR}/temporal-$(date -u +%Y%m%dT%H%M%SZ).sql}"
backup_database "${backup_path}" >/dev/null

trap - EXIT
restore_initial_runtime_state

printf 'Temporal backup written to %s\n' "${backup_path}"
printf 'Backup manifest written to %s.manifest.json\n' "${backup_path}"
