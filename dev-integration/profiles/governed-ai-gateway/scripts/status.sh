#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

print_status

if is_active_profile && command -v k3s >/dev/null 2>&1; then
  kubectl_cmd get deploy,svc,pvc -n "${NAMESPACE}" -l dev-integration-profile="${PROFILE_ID}" 2>/dev/null || true
  kubectl_cmd get deploy,svc -n "${CONSUMER_NAMESPACE}" 2>/dev/null || true
  kubectl_cmd get deploy,svc -n "${PROVIDER_NAMESPACE}" 2>/dev/null || true
fi
