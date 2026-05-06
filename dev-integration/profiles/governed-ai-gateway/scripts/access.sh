#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile
need_cmd k3s

wait_for_runtime_ready

printf 'governed-ai-gateway API: http://localhost:%s\n' "${ACCESS_LOCAL_PORT}"
kubectl_cmd -n "${NAMESPACE}" port-forward "svc/${GATEWAY_SERVICE}" "${ACCESS_LOCAL_PORT}:8080"
