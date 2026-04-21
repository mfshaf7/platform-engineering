#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
OPENPROJECT_ADMIN_SECRET_NAME="${OPENPROJECT_ADMIN_SECRET_NAME:-openproject-admin-secret}"
OPENPROJECT_ADMIN_PASSWORD_KEY="${OPENPROJECT_ADMIN_PASSWORD_KEY:-password}"
OPENPROJECT_ADMIN_LOGIN="${OPENPROJECT_ADMIN_LOGIN:-admin}"
OPENPROJECT_ADMIN_FORCE_PASSWORD_CHANGE="${OPENPROJECT_ADMIN_FORCE_PASSWORD_CHANGE:-true}"

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
need_cmd base64

echo "Waiting for OpenProject web deployment rollout"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" rollout status "deploy/${OPENPROJECT_DEPLOYMENT}" --timeout=300s >/dev/null

echo "Reading admin password from Kubernetes secret ${OPENPROJECT_ADMIN_SECRET_NAME}"
admin_password="$(
  kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" get secret "${OPENPROJECT_ADMIN_SECRET_NAME}" \
    -o "jsonpath={.data.${OPENPROJECT_ADMIN_PASSWORD_KEY}}" | base64 -d
)"

if [[ -z "${admin_password}" ]]; then
  echo "Admin password secret ${OPENPROJECT_ADMIN_SECRET_NAME}/${OPENPROJECT_ADMIN_PASSWORD_KEY} is empty" >&2
  exit 1
fi

if (( ${#admin_password} < 10 )); then
  echo "OpenProject requires admin passwords to be at least 10 characters; current Vault-backed value is too short" >&2
  exit 1
fi

echo "Syncing OpenProject admin password for ${OPENPROJECT_ADMIN_LOGIN}"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec "deploy/${OPENPROJECT_DEPLOYMENT}" -- \
  env TARGET_PASSWORD="${admin_password}" TARGET_LOGIN="${OPENPROJECT_ADMIN_LOGIN}" TARGET_FORCE_PASSWORD_CHANGE="${OPENPROJECT_ADMIN_FORCE_PASSWORD_CHANGE}" bash -lc \
  'bundle exec rails runner '\''user = User.find_by!(login: ENV.fetch("TARGET_LOGIN"))
password = ENV.fetch("TARGET_PASSWORD")
force_password_change = ENV.fetch("TARGET_FORCE_PASSWORD_CHANGE", "true") == "true"
user.password = password
user.password_confirmation = password
user.force_password_change = force_password_change
user.save!
user.reload
raise "Password verification failed" unless user.check_password?(password)
puts({login: user.login, force_password_change: user.force_password_change?, password_verified: true}.inspect)
'\'''
