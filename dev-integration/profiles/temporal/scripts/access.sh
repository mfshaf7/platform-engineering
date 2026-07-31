#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile "access"
need_cmd k3s

kubectl_cmd -n "${NAMESPACE}" rollout status \
  "deployment/${UI_DEPLOYMENT}" --timeout=300s
printf 'Temporal diagnostic UI: http://localhost:%s\n' "${ACCESS_LOCAL_PORT}"
printf 'This operator-local port-forward does not create public ingress.\n'
kubectl_cmd -n "${NAMESPACE}" port-forward \
  "service/${UI_SERVICE}" "${ACCESS_LOCAL_PORT}:8080"
