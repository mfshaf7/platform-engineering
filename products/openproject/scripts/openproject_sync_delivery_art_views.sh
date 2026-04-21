#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_sync_delivery_art_views_runner.rb"
OPENPROJECT_DELIVERY_PI_NAMES="${OPENPROJECT_DELIVERY_PI_NAMES:-}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

openproject_pod() {
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get pod \
    -l "app.kubernetes.io/component=web,app.kubernetes.io/name=openproject" \
    -o jsonpath='{.items[0].metadata.name}'
}

need_cmd "${KUBECTL%% *}"

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

pod_name="$(openproject_pod)"

echo "Synchronizing OpenProject delivery ART views in ${OPENPROJECT_NAMESPACE}/${pod_name}"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec -i "${pod_name}" -- env \
  OPENPROJECT_DELIVERY_PI_NAMES="${OPENPROJECT_DELIVERY_PI_NAMES}" \
  sh -lc '
set -euo pipefail
tmp_script="/tmp/openproject_sync_delivery_art_views_runner.rb"
cat > "${tmp_script}"
bundle exec rails runner "${tmp_script}"
rm -f "${tmp_script}"
' <"${RUNNER_SCRIPT}"
