#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile "down"
need_cmd k3s

namespace_result=""
if namespace_result="$(kubectl_cmd get namespace "${NAMESPACE}" -o name 2>&1)"; then
  scale_temporal_deployments 0
  wait_for_temporal_deployments_suspended
  kubectl_cmd -n "${NAMESPACE}" scale \
    "statefulset/${POSTGRESQL_STATEFULSET}" --replicas=0 >/dev/null 2>&1 || true
  wait_for_zero_replicas "statefulset/${POSTGRESQL_STATEFULSET}"
elif [[ "${namespace_result}" != *"NotFound"* \
  && "${namespace_result}" != *"not found"* ]]; then
  printf 'refused: Kubernetes namespace query failed: %s\n' \
    "${namespace_result}" >&2
  exit 1
fi
write_status_file
printf 'Temporal dev-integration runtime suspended or absent; preserved state was not reset\n'
