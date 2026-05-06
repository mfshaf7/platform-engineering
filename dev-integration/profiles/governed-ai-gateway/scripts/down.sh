#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile
need_cmd k3s

kubectl_cmd -n "${CONSUMER_NAMESPACE}" scale deployment "${CONSUMER_DEPLOYMENT}" --replicas=0 >/dev/null 2>&1 || true
kubectl_cmd -n "${PROVIDER_NAMESPACE}" scale deployment "${PROVIDER_DEPLOYMENT}" --replicas=0 >/dev/null 2>&1 || true
kubectl_cmd -n "${NAMESPACE}" scale deployment "${GATEWAY_DEPLOYMENT}" --replicas=0 >/dev/null 2>&1 || true
write_status_file
printf 'governed-ai-gateway dev-integration profile suspended; local PVC and secrets preserved\n'
