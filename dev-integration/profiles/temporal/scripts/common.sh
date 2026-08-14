#!/usr/bin/env bash
set -euo pipefail

readonly PROFILE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly OWNER_REPO_ROOT="$(cd "${PROFILE_ROOT}/../../.." && pwd)"
readonly RUNTIME_ROOT="${PROFILE_ROOT}/runtime"
readonly ARTIFACT_LOCK="${RUNTIME_ROOT}/artifact-lock.yaml"
readonly BOUNDARY_CONTRACT="${RUNTIME_ROOT}/boundary-contract.yaml"
readonly PROFILE_ID="${DEVINT_PROFILE_ID:-temporal}"
readonly OPERATOR="${DEVINT_OPERATOR:-${USER:-operator}}"
readonly OPERATOR_SLUG="$(
  python3 - "${OPERATOR}" <<'PY'
import re
import sys

value = re.sub(r"[^a-z0-9-]+", "-", sys.argv[1].lower())
value = re.sub(r"-{2,}", "-", value).strip("-")
print(value or "operator")
PY
)"
readonly NAMESPACE="${DEVINT_NAMESPACE:-devint-${PROFILE_ID}-${OPERATOR_SLUG}}"
readonly STATE_ROOT="${DEVINT_STATE_ROOT:-${OWNER_REPO_ROOT}/.dev-integration/${PROFILE_ID}/${OPERATOR_SLUG}}"
readonly SESSION_FILE="${DEVINT_SESSION_FILE:-${STATE_ROOT}/current-session.yaml}"
readonly PROMOTION_REPORT="${DEVINT_PROMOTION_REPORT:-${STATE_ROOT}/promotion-report.yaml}"
readonly DEVINT_KUBECONFIG_PATH="${DEVINT_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

export KUBECONFIG="${DEVINT_KUBECONFIG_PATH}"
read -r -a KUBECTL_CMD <<<"${DEVINT_KUBECTL:-k3s kubectl}"

readonly STATUS_FILE="${STATE_ROOT}/profile-status.txt"
readonly SMOKE_SUMMARY="${STATE_ROOT}/smoke-summary.json"
readonly PROFILE_PROMOTION_NOTES="${STATE_ROOT}/profile-promotion-notes.md"
readonly RENDERED_DIR="${STATE_ROOT}/rendered"
readonly ARTIFACTS_DIR="${STATE_ROOT}/artifacts"
readonly LOGS_DIR="${STATE_ROOT}/logs"
readonly BACKUPS_DIR="${STATE_ROOT}/backups"
readonly LOCAL_SECRETS_ENV="${STATE_ROOT}/local-secrets.env"
readonly DEVINT_BASE_ROOT="$(dirname "$(dirname "${STATE_ROOT}")")"
readonly ARCHIVE_ROOT="${DEVINT_BASE_ROOT}/archives/${PROFILE_ID}/${OPERATOR_SLUG}"

readonly RELEASE_NAME="temporal"
readonly POSTGRESQL_STATEFULSET="temporal-postgresql"
readonly POSTGRESQL_SECRET="temporal-postgresql"
readonly UI_DEPLOYMENT="temporal-web"
readonly UI_SERVICE="temporal-web"
readonly FRONTEND_SERVICE="temporal-frontend"
readonly ACCESS_LOCAL_PORT="${DEVINT_TEMPORAL_UI_LOCAL_PORT:-18233}"
readonly -a TEMPORAL_DEPLOYMENTS=(
  temporal-frontend
  temporal-history
  temporal-matching
  temporal-worker
  temporal-admintools
  temporal-web
)

yaml_value() {
  local path="$1"
  local dotted_key="$2"
  python3 - "${path}" "${dotted_key}" <<'PY'
import pathlib
import sys
import yaml

value = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}

readonly CHART_NAME="$(yaml_value "${ARTIFACT_LOCK}" chart.name)"
readonly CHART_REPOSITORY="$(yaml_value "${ARTIFACT_LOCK}" chart.repository)"
readonly CHART_VERSION="$(yaml_value "${ARTIFACT_LOCK}" chart.version)"
readonly CHART_SHA256="$(yaml_value "${ARTIFACT_LOCK}" chart.sha256)"
readonly CHART_ARCHIVE="${ARTIFACTS_DIR}/${CHART_NAME}-${CHART_VERSION}.tgz"
if [[ -n "${DEVINT_TEMPORAL_WORKFLOW_NAMESPACE:-}" ]]; then
  readonly TEMPORAL_WORKFLOW_NAMESPACE="${DEVINT_TEMPORAL_WORKFLOW_NAMESPACE}"
else
  readonly TEMPORAL_WORKFLOW_NAMESPACE="$(
    python3 - "${BOUNDARY_CONTRACT}" "${OPERATOR}" <<'PY'
import hashlib
import pathlib
import re
import sys
import yaml

contract = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
runtime = contract["runtime"]
pattern = runtime["temporal_namespace_pattern"]
maximum = runtime["temporal_namespace_max_length"]
prefix, marker, suffix_text = pattern.partition("{operator}")
if marker != "{operator}" or suffix_text:
    raise SystemExit("Temporal namespace pattern must end with {operator}")
prefix = re.sub(r"[^a-z0-9-]+", "-", prefix.lower()).strip("-")
operator = sys.argv[2]
slug = re.sub(r"[^a-z0-9-]+", "-", operator.lower())
slug = re.sub(r"-{2,}", "-", slug).strip("-")
if not prefix or not slug:
    raise SystemExit("Temporal workflow namespace rendered empty")
candidate = f"{prefix}-{slug}"
if len(candidate) <= maximum and slug == operator:
    print(candidate)
else:
    digest = hashlib.sha256(operator.encode("utf-8")).hexdigest()[:12]
    head_length = maximum - len(prefix) - len(digest) - 2
    head = slug[:head_length].rstrip("-")
    if not head:
        raise SystemExit("Temporal workflow namespace cannot fit its chart budget")
    print(f"{prefix}-{head}-{digest}")
PY
  )"
fi

kubectl_cmd() {
  "${KUBECTL_CMD[@]}" "$@"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_state_dirs() {
  mkdir -p "${STATE_ROOT}" "${RENDERED_DIR}" "${ARTIFACTS_DIR}" "${LOGS_DIR}" "${BACKUPS_DIR}"
}

profile_lifecycle() {
  if [[ -n "${DEVINT_PROFILE_LIFECYCLE:-}" ]]; then
    printf '%s' "${DEVINT_PROFILE_LIFECYCLE}"
    return
  fi

  if [[ -f "${SESSION_FILE}" ]]; then
    python3 - "${SESSION_FILE}" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
match = re.search(r"(?m)^profile_lifecycle:\s*['\"]?([^'\"\n]+)['\"]?\s*$", text)
print(match.group(1).strip() if match else "build-admitted")
PY
    return
  fi

  printf 'build-admitted'
}

readonly PROFILE_LIFECYCLE="$(profile_lifecycle)"

is_active_profile() {
  [[ "${PROFILE_LIFECYCLE}" == "active" ]]
}

render_status() {
  cat <<EOF
profile: ${PROFILE_ID}
lifecycle: ${PROFILE_LIFECYCLE}
kubernetes namespace: ${NAMESPACE}
temporal namespace: ${TEMPORAL_WORKFLOW_NAMESPACE}
operator: ${OPERATOR}
state root: ${STATE_ROOT}
runtime state: $(runtime_state)
source implementation: defined
source implementation authorized: true
runtime launch authorized: $(is_active_profile && printf 'true' || printf 'false')
workflow execution authorized: ${DEVINT_TEMPORAL_WORKFLOW_EXECUTION_AUTHORIZED:-false}
public ingress: false
diagnostic access: operator-local port-forward
chart: ${CHART_NAME}-${CHART_VERSION}
chart sha256: ${CHART_SHA256}
aggregate orchestrator: operator-orchestration-service
EOF
}

write_status_file() {
  ensure_state_dirs
  render_status >"${STATUS_FILE}"
}

print_status() {
  render_status
}

fail_not_active() {
  write_status_file
  cat "${STATUS_FILE}"
  printf '\nrefused: %s is %s, not active; runtime action %s remains intentionally blocked\n' \
    "${PROFILE_ID}" "${PROFILE_LIFECYCLE}" "${1:-unknown}" >&2
  exit 2
}

require_active_profile() {
  local action="${1:-runtime}"
  if ! is_active_profile; then
    fail_not_active "${action}"
  fi
}

source "${PROFILE_ROOT}/scripts/lib/runtime.sh"
source "${PROFILE_ROOT}/scripts/lib/persistence.sh"

confirm_exact() {
  local actual="$1"
  local expected="$2"
  local action="$3"
  if [[ "${actual}" != "${expected}" ]]; then
    printf 'refused: %s requires CONFIRM=%s\n' "${action}" "${expected}" >&2
    exit 2
  fi
}
