#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile
need_cmd k3s

kubectl_cmd delete namespace "${CONSUMER_NAMESPACE}" --ignore-not-found=true
kubectl_cmd delete namespace "${PROVIDER_NAMESPACE}" --ignore-not-found=true
kubectl_cmd delete namespace "${NAMESPACE}" --ignore-not-found=true
rm -rf "${STATE_ROOT}"
printf 'governed-ai-gateway dev-integration profile reset; namespace and local state removed\n'
