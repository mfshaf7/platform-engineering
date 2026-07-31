#!/usr/bin/env bash
set -euo pipefail

readonly PROFILE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly OWNER_REPO_ROOT="$(cd "${PROFILE_ROOT}/../../.." && pwd)"
readonly PROFILE_ID="${DEVINT_PROFILE_ID:-temporal}"
readonly OPERATOR="${DEVINT_OPERATOR:-${USER:-operator}}"
readonly NAMESPACE="${DEVINT_NAMESPACE:-devint-${PROFILE_ID}-${OPERATOR}}"
readonly STATE_ROOT="${DEVINT_STATE_ROOT:-${OWNER_REPO_ROOT}/.dev-integration/${PROFILE_ID}/${OPERATOR}}"
readonly SESSION_FILE="${DEVINT_SESSION_FILE:-${STATE_ROOT}/current-session.yaml}"
readonly STATUS_FILE="${STATE_ROOT}/profile-status.txt"
readonly SMOKE_SUMMARY="${STATE_ROOT}/smoke-summary.json"
readonly PROFILE_PROMOTION_NOTES="${STATE_ROOT}/profile-promotion-notes.md"

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
print(match.group(1).strip() if match else "proposed")
PY
    return
  fi

  printf 'proposed'
}

readonly PROFILE_LIFECYCLE="$(profile_lifecycle)"

ensure_state_dir() {
  mkdir -p "${STATE_ROOT}"
}

write_status_file() {
  ensure_state_dir
  cat >"${STATUS_FILE}" <<EOF
profile: ${PROFILE_ID}
lifecycle: ${PROFILE_LIFECYCLE}
namespace: ${NAMESPACE}
operator: ${OPERATOR}
state root: ${STATE_ROOT}
runtime: not-implemented
launchable: false
implementation authorized: false
stage or production authorized: false
aggregate orchestrator: operator-orchestration-service
EOF
}

print_status() {
  write_status_file
  cat "${STATUS_FILE}"
}

deny_runtime_action() {
  local action="$1"
  print_status
  printf '\nrefused: temporal profile action %s is unavailable while the profile is proposed and the runtime is not implemented\n' "${action}" >&2
  exit 2
}
