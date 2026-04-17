#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNNER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_configure_idea_backlog_runner.rb"

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

if [[ ! -f "${RUNNER_SCRIPT}" ]]; then
  echo "Missing runner script: ${RUNNER_SCRIPT}" >&2
  exit 1
fi

echo "Configuring OpenProject idea backlog model in ${OPENPROJECT_NAMESPACE}/${OPENPROJECT_DEPLOYMENT}"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec -i "deploy/${OPENPROJECT_DEPLOYMENT}" -- sh -lc '
set -euo pipefail
tmp_script="/tmp/openproject_configure_idea_backlog_runner.rb"
cat > "${tmp_script}"
bundle exec rails runner "${tmp_script}"
rm -f "${tmp_script}"
' <"${RUNNER_SCRIPT}"
