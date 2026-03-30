#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
ARGO_NAMESPACE="${ARGO_NAMESPACE:-argocd}"
VAULT_NAMESPACE="${VAULT_NAMESPACE:-vault}"
VAULT_POD="${VAULT_POD:-vault-0}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
OPERATOR_USERNAME="${OPERATOR_USERNAME:-}"
OPERATOR_PASSWORD="${OPERATOR_PASSWORD:-}"

if [[ -z "${OPERATOR_USERNAME}" || -z "${OPERATOR_PASSWORD}" ]]; then
  echo "OPERATOR_USERNAME and OPERATOR_PASSWORD must be set" >&2
  exit 1
fi

if [[ -z "${VAULT_TOKEN:-}" ]]; then
  echo "VAULT_TOKEN must be set" >&2
  exit 1
fi

vault_exec() {
  ${KUBECTL} -n "${VAULT_NAMESPACE}" exec "${VAULT_POD}" -- \
    env VAULT_ADDR="${VAULT_ADDR}" VAULT_TOKEN="${VAULT_TOKEN}" \
    OPERATOR_USERNAME="${OPERATOR_USERNAME}" OPERATOR_PASSWORD="${OPERATOR_PASSWORD}" \
    "$@"
}

argocd_exec() {
  ${KUBECTL} -n "${ARGO_NAMESPACE}" exec deploy/argocd-server -- \
    env OPERATOR_PASSWORD="${OPERATOR_PASSWORD}" \
    "$@"
}

if ! vault_exec vault status >/dev/null 2>&1; then
  echo "Vault is not reachable with the supplied VAULT_TOKEN and VAULT_ADDR" >&2
  exit 1
fi

if ! vault_exec vault auth list -format=json | grep -q '"userpass/"'; then
  vault_exec vault auth enable userpass
fi

vault_exec sh -ceu '
  cat <<EOF >/tmp/platform-admin.hcl
path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo", "patch"]
}
EOF
  vault policy write platform-admin /tmp/platform-admin.hcl
  vault write auth/userpass/users/"$OPERATOR_USERNAME" \
    password="$OPERATOR_PASSWORD" \
    policies=platform-admin
'

password_hash="$(argocd_exec sh -ceu 'argocd account bcrypt --password "$OPERATOR_PASSWORD"' | tr -d '\r\n')"
password_hash_b64="$(printf '%s' "${password_hash}" | base64 -w0)"
password_mtime_b64="$(date -u +%Y-%m-%dT%H:%M:%SZ | tr -d '\r\n' | base64 -w0)"

accounts_value="$(${KUBECTL} -n "${ARGO_NAMESPACE}" get configmap argocd-cm -o jsonpath="{.data.accounts\.${OPERATOR_USERNAME}}" 2>/dev/null || true)"
if [[ "${accounts_value}" != "login,apiKey" ]]; then
  ${KUBECTL} -n "${ARGO_NAMESPACE}" patch configmap argocd-cm --type merge \
    -p "{\"data\":{\"accounts.${OPERATOR_USERNAME}\":\"login,apiKey\"}}"
fi

existing_policy="$(${KUBECTL} -n "${ARGO_NAMESPACE}" get configmap argocd-rbac-cm -o jsonpath='{.data.policy\.csv}' 2>/dev/null || true)"
policy_line="g, ${OPERATOR_USERNAME}, role:admin"
if ! printf '%s\n' "${existing_policy}" | grep -Fxq "${policy_line}"; then
  if [[ -n "${existing_policy}" ]]; then
    updated_policy="${existing_policy}"$'\n'"${policy_line}"
  else
    updated_policy="${policy_line}"
  fi
  escaped_policy="${updated_policy//$'\n'/\\n}"
  ${KUBECTL} -n "${ARGO_NAMESPACE}" patch configmap argocd-rbac-cm --type merge \
    -p "{\"data\":{\"policy.csv\":\"${escaped_policy}\"}}"
fi

${KUBECTL} -n "${ARGO_NAMESPACE}" patch secret argocd-secret --type merge \
  -p "{\"data\":{\"accounts.${OPERATOR_USERNAME}.password\":\"${password_hash_b64}\",\"accounts.${OPERATOR_USERNAME}.passwordMtime\":\"${password_mtime_b64}\"}}"

${KUBECTL} -n "${ARGO_NAMESPACE}" rollout restart deploy/argocd-server deploy/argocd-repo-server statefulset/argocd-application-controller >/dev/null
${KUBECTL} -n "${ARGO_NAMESPACE}" rollout status deploy/argocd-server --timeout=120s >/dev/null
${KUBECTL} -n "${ARGO_NAMESPACE}" rollout status deploy/argocd-repo-server --timeout=120s >/dev/null
${KUBECTL} -n "${ARGO_NAMESPACE}" rollout status statefulset/argocd-application-controller --timeout=120s >/dev/null

echo "Configured operator access for Argo CD and Vault: ${OPERATOR_USERNAME}"
