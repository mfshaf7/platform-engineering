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
OPENPROJECT_URL="${OPENPROJECT_URL:-http://127.0.0.1:32083/login}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

need_cmd "${KUBECTL%% *}"
need_cmd curl

echo "Argo CD applications"
kubectl_cmd -n "${ARGO_NAMESPACE}" get applications "${POSTGRES_SECRETS_APP_NAME}" "${POSTGRES_APP_NAME}" "${SECRETS_APP_NAME}" "${APP_NAME}"
echo

echo "Standalone PostgreSQL namespace resources"
kubectl_cmd -n "${POSTGRES_NAMESPACE}" get pods
echo
kubectl_cmd -n "${POSTGRES_NAMESPACE}" get svc,pvc,secret,externalsecret,secretstore,sa
echo

echo "OpenProject namespace resources"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get pods
echo
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get svc,pvc,externalsecret,secretstore,sa
echo

if curl -fsSI "${OPENPROJECT_URL}" >/dev/null 2>&1; then
  echo "OpenProject URL reachable: ${OPENPROJECT_URL}"
else
  echo "OpenProject URL not reachable yet: ${OPENPROJECT_URL}" >&2
fi
