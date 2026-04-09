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
PURGE_DATA="${PURGE_DATA:-false}"
FORCE="${FORCE:-false}"
REMOVE_POSTGRES="${REMOVE_POSTGRES:-false}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD_KUSTOMIZATION="${REPO_ROOT}/environments/prod/argocd/kustomization.yaml"

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
need_cmd rg

if rg -n "openproject-secrets-app.yaml|openproject-app.yaml" "${PROD_KUSTOMIZATION}" >/dev/null 2>&1 && [[ "${FORCE}" != "true" ]]; then
  echo "OpenProject is still declared in GitOps at ${PROD_KUSTOMIZATION}." >&2
  echo "Remove the OpenProject app entries from Git and reconcile platform-root-prod before running uninstall." >&2
  echo "If you only want a temporary live-cluster removal, rerun with FORCE=true." >&2
  exit 1
fi

if [[ "${REMOVE_POSTGRES}" == "true" ]] && rg -n "platform-postgresql-secrets-app.yaml|platform-postgresql-app.yaml" "${PROD_KUSTOMIZATION}" >/dev/null 2>&1 && [[ "${FORCE}" != "true" ]]; then
  echo "Standalone PostgreSQL is still declared in GitOps at ${PROD_KUSTOMIZATION}." >&2
  echo "Remove the platform-postgresql app entries from Git and reconcile platform-root-prod before removing the shared database." >&2
  echo "If you only want a temporary live-cluster removal, rerun with FORCE=true REMOVE_POSTGRES=true." >&2
  exit 1
fi

echo "Deleting Argo CD applications"
kubectl_cmd -n "${ARGO_NAMESPACE}" delete application "${APP_NAME}" "${SECRETS_APP_NAME}" --ignore-not-found

if [[ "${REMOVE_POSTGRES}" == "true" ]]; then
  echo "Deleting standalone PostgreSQL Argo CD applications"
  kubectl_cmd -n "${ARGO_NAMESPACE}" delete application "${POSTGRES_APP_NAME}" "${POSTGRES_SECRETS_APP_NAME}" --ignore-not-found
fi

if [[ "${PURGE_DATA}" == "true" ]]; then
  echo "Deleting namespace ${OPENPROJECT_NAMESPACE}"
  kubectl_cmd delete namespace "${OPENPROJECT_NAMESPACE}" --ignore-not-found
  if [[ "${REMOVE_POSTGRES}" == "true" ]]; then
    echo "Deleting namespace ${POSTGRES_NAMESPACE}"
    kubectl_cmd delete namespace "${POSTGRES_NAMESPACE}" --ignore-not-found
  fi
else
  echo "Leaving namespace and PVC data in place."
  echo "Remaining namespace resources:"
  kubectl_cmd get namespace "${OPENPROJECT_NAMESPACE}" >/dev/null 2>&1 && kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get pvc,secret,externalsecret || true
  if [[ "${REMOVE_POSTGRES}" == "true" ]]; then
    kubectl_cmd get namespace "${POSTGRES_NAMESPACE}" >/dev/null 2>&1 && kubectl_cmd -n "${POSTGRES_NAMESPACE}" get pvc,secret,externalsecret || true
  fi
fi
