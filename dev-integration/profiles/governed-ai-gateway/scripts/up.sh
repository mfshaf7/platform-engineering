#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile
need_cmd k3s
need_cmd python3

ensure_state_dirs
render_runtime_manifest

kubectl_cmd apply -f "${RENDERED_DIR}/governed-ai-gateway-runtime.yaml"
kubectl_cmd -n "${NAMESPACE}" rollout restart "deployment/${GATEWAY_DEPLOYMENT}" >/dev/null 2>&1 || true
wait_for_runtime_ready

write_status_file
printf 'governed-ai-gateway dev-integration profile ready\n'
printf 'namespace: %s\n' "${NAMESPACE}"
printf 'consumer namespace: %s\n' "${CONSUMER_NAMESPACE}"
printf 'provider sentinel namespace: %s\n' "${PROVIDER_NAMESPACE}"
printf 'gateway: svc/%s\n' "${GATEWAY_SERVICE}"
