#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
VAULT_NAMESPACE="${VAULT_NAMESPACE:-vault}"
VAULT_POD="${VAULT_POD:-vault-0}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

if [[ -z "${VAULT_TOKEN:-}" ]]; then
  echo "VAULT_TOKEN must be set" >&2
  exit 1
fi

vault_exec() {
  ${KUBECTL} -n "${VAULT_NAMESPACE}" exec "${VAULT_POD}" -- env VAULT_ADDR="${VAULT_ADDR}" VAULT_TOKEN="${VAULT_TOKEN}" "$@"
}

if ! vault_exec vault status >/dev/null 2>&1; then
  echo "Vault is not reachable with the supplied VAULT_TOKEN and VAULT_ADDR" >&2
  exit 1
fi

if ! vault_exec vault secrets list -format=json | grep -q '"kv/"'; then
  vault_exec vault secrets enable -path=kv kv-v2
fi

if ! vault_exec vault auth list -format=json | grep -q '"kubernetes/"'; then
  vault_exec vault auth enable kubernetes
fi

vault_exec sh -ceu '
  vault write auth/kubernetes/config \
    token_reviewer_jwt="$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" \
    kubernetes_host="https://${KUBERNETES_PORT_443_TCP_ADDR}:443" \
    kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt

  cat <<EOF >/tmp/platform-stage-read.hcl
path "kv/data/products/openclaw/stage/*" {
  capabilities = ["read"]
}

path "kv/metadata/products/openclaw/stage/*" {
  capabilities = ["read", "list"]
}
EOF
  vault policy write platform-stage-read /tmp/platform-stage-read.hcl

  cat <<EOF >/tmp/platform-prod-read.hcl
path "kv/data/products/openclaw/prod/*" {
  capabilities = ["read"]
}

path "kv/metadata/products/openclaw/prod/*" {
  capabilities = ["read", "list"]
}
EOF
  vault policy write platform-prod-read /tmp/platform-prod-read.hcl

  cat <<EOF >/tmp/platform-observability-stage-read.hcl
path "kv/data/platform/observability/stage/*" {
  capabilities = ["read"]
}

path "kv/metadata/platform/observability/stage/*" {
  capabilities = ["read", "list"]
}
EOF
  vault policy write platform-observability-stage-read /tmp/platform-observability-stage-read.hcl

  cat <<EOF >/tmp/platform-observability-prod-read.hcl
path "kv/data/platform/observability/prod/*" {
  capabilities = ["read"]
}

path "kv/metadata/platform/observability/prod/*" {
  capabilities = ["read", "list"]
}
EOF
  vault policy write platform-observability-prod-read /tmp/platform-observability-prod-read.hcl

  vault write auth/kubernetes/role/platform-stage-secrets \
    bound_service_account_names="platform-vault-reader" \
    bound_service_account_namespaces="openclaw-stage" \
    audience="vault" \
    token_policies="platform-stage-read" \
    ttl="1h"

  vault write auth/kubernetes/role/platform-prod-secrets \
    bound_service_account_names="platform-vault-reader" \
    bound_service_account_namespaces="openclaw" \
    audience="vault" \
    token_policies="platform-prod-read" \
    ttl="1h"

  vault write auth/kubernetes/role/platform-observability-stage-secrets \
    bound_service_account_names="platform-vault-reader" \
    bound_service_account_namespaces="observability-stage" \
    audience="vault" \
    token_policies="platform-observability-stage-read" \
    ttl="1h"

  vault write auth/kubernetes/role/platform-observability-prod-secrets \
    bound_service_account_names="platform-vault-reader" \
    bound_service_account_namespaces="observability" \
    audience="vault" \
    token_policies="platform-observability-prod-read" \
    ttl="1h"
'
