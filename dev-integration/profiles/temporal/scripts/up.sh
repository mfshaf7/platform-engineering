#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_active_profile "up"
need_cmd helm
need_cmd k3s
need_cmd python3
need_cmd sha256sum

render_runtime
ensure_chart

kubectl_cmd create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl_cmd apply -f -
kubectl_cmd label namespace "${NAMESPACE}" \
  app.kubernetes.io/part-of=temporal \
  dev-integration-profile=temporal \
  "dev-integration-operator=${OPERATOR_SLUG}" \
  --overwrite
apply_database_secret
kubectl_cmd apply -f "${RENDERED_DIR}/postgresql.yaml"
kubectl_cmd apply -f "${RENDERED_DIR}/network-boundaries.yaml"
wait_for_postgresql

helm upgrade --install "${RELEASE_NAME}" "${CHART_ARCHIVE}" \
  --namespace "${NAMESPACE}" \
  --values "${RENDERED_DIR}/temporal-values.yaml" \
  --atomic \
  --timeout 10m \
  --wait

wait_for_runtime_ready
write_status_file
printf 'Temporal dev-integration runtime ready\n'
printf 'Kubernetes namespace: %s\n' "${NAMESPACE}"
printf 'Temporal namespace: %s\n' "${TEMPORAL_WORKFLOW_NAMESPACE}"
printf 'Frontend service: %s:7233\n' "${FRONTEND_SERVICE}"
printf 'Diagnostic UI: use make devint-access PROFILE=temporal\n'
