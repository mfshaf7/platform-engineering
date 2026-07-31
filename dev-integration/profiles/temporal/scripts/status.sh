#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

print_status

if command -v k3s >/dev/null 2>&1 \
  && kubectl_cmd get namespace "${NAMESPACE}" >/dev/null 2>&1; then
  printf '\nRuntime resources:\n'
  kubectl_cmd -n "${NAMESPACE}" get deploy,statefulset,svc,pvc \
    -l app.kubernetes.io/part-of=temporal 2>/dev/null || true
fi
