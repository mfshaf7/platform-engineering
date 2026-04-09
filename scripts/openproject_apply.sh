#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
ARGO_NAMESPACE="${ARGO_NAMESPACE:-argocd}"
POSTGRES_NAMESPACE="${POSTGRES_NAMESPACE:-platform-postgresql}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
POSTGRES_APP_NAME="${POSTGRES_APP_NAME:-platform-postgresql}"
POSTGRES_SECRETS_APP_NAME="${POSTGRES_SECRETS_APP_NAME:-platform-postgresql-secrets}"
APP_NAME="${APP_NAME:-openproject}"
SECRETS_APP_NAME="${SECRETS_APP_NAME:-openproject-secrets}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_SECRETS_APP_MANIFEST="${REPO_ROOT}/environments/prod/argocd/platform-postgresql-secrets-app.yaml"
POSTGRES_APP_MANIFEST="${REPO_ROOT}/environments/prod/argocd/platform-postgresql-app.yaml"
SECRETS_APP_MANIFEST="${REPO_ROOT}/environments/prod/argocd/openproject-secrets-app.yaml"
APP_MANIFEST="${REPO_ROOT}/environments/prod/argocd/openproject-app.yaml"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

jsonpath_value() {
  local namespace="$1"
  local name="$2"
  local path="$3"
  kubectl_cmd -n "${namespace}" get application "${name}" -o "jsonpath=${path}" 2>/dev/null || true
}

wait_for_application() {
  local name="$1"
  local timeout_seconds="${2:-600}"
  local start
  start="$(date +%s)"

  while true; do
    local sync_status health_status
    sync_status="$(jsonpath_value "${ARGO_NAMESPACE}" "${name}" '{.status.sync.status}')"
    health_status="$(jsonpath_value "${ARGO_NAMESPACE}" "${name}" '{.status.health.status}')"

    if [[ "${sync_status}" == "Synced" && "${health_status}" == "Healthy" ]]; then
      echo "Application ${name} is Synced and Healthy"
      return 0
    fi

    if (( "$(date +%s)" - start >= timeout_seconds )); then
      echo "Timed out waiting for ${name}. Current sync=${sync_status:-unknown} health=${health_status:-unknown}" >&2
      return 1
    fi

    echo "Waiting for ${name}: sync=${sync_status:-unknown} health=${health_status:-unknown}"
    sleep 10
  done
}

need_cmd "${KUBECTL%% *}"

echo "Applying standalone PostgreSQL secret-delivery app manifest"
kubectl_cmd apply -f "${POSTGRES_SECRETS_APP_MANIFEST}"
wait_for_application "${POSTGRES_SECRETS_APP_NAME}" 300

echo "Applying standalone PostgreSQL app manifest"
kubectl_cmd apply -f "${POSTGRES_APP_MANIFEST}"
wait_for_application "${POSTGRES_APP_NAME}" 900

echo "Applying OpenProject secret-delivery app manifest"
kubectl_cmd apply -f "${SECRETS_APP_MANIFEST}"
wait_for_application "${SECRETS_APP_NAME}" 300

echo "Applying OpenProject application manifest"
kubectl_cmd apply -f "${APP_MANIFEST}"
wait_for_application "${APP_NAME}" 900

echo
kubectl_cmd -n "${POSTGRES_NAMESPACE}" get pods
echo
kubectl_cmd -n "${POSTGRES_NAMESPACE}" get svc,pvc,secret
echo
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get pods
echo
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get svc,pvc
