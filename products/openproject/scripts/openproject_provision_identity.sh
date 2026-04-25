#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
VAULT_NAMESPACE="${VAULT_NAMESPACE:-vault}"
VAULT_POD="${VAULT_POD:-vault-0}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

TARGET_LOGIN="${TARGET_LOGIN:?TARGET_LOGIN must be set}"
TARGET_FIRSTNAME="${TARGET_FIRSTNAME:?TARGET_FIRSTNAME must be set}"
TARGET_LASTNAME="${TARGET_LASTNAME:?TARGET_LASTNAME must be set}"
TARGET_MAIL="${TARGET_MAIL:?TARGET_MAIL must be set}"
TARGET_PROJECT_IDENTIFIER="${TARGET_PROJECT_IDENTIFIER:-workspace-delivery-art}"
TARGET_PROJECT_IDENTIFIERS_JSON="${TARGET_PROJECT_IDENTIFIERS_JSON:-}"
TARGET_TOKEN_NAME="${TARGET_TOKEN_NAME:-openproject-${TARGET_LOGIN}-v1}"
TARGET_ROLE_NAMES_JSON="${TARGET_ROLE_NAMES_JSON:-[\"Reader\"]}"
ROTATE_API_TOKEN="${ROTATE_API_TOKEN:-false}"
ISSUE_API_TOKEN="${ISSUE_API_TOKEN:-false}"
VAULT_SECRET_PATH="${VAULT_SECRET_PATH:-}"
OPENPROJECT_API_TOKEN_OUTPUT_PATH="${OPENPROJECT_API_TOKEN_OUTPUT_PATH:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ADAPTER_SCRIPT="${REPO_ROOT}/products/openproject/scripts/openproject_platform_admin_adapter.py"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

vault_cmd() {
  kubectl_cmd -n "${VAULT_NAMESPACE}" exec "${VAULT_POD}" -- env VAULT_ADDR="${VAULT_ADDR}" VAULT_TOKEN="${VAULT_TOKEN}" "$@"
}

need_cmd "${KUBECTL%% *}"
need_cmd python3

if [[ "${ISSUE_API_TOKEN}" == "true" && -z "${VAULT_SECRET_PATH}" && -z "${OPENPROJECT_API_TOKEN_OUTPUT_PATH}" ]]; then
  echo "Set VAULT_SECRET_PATH and VAULT_TOKEN, or set OPENPROJECT_API_TOKEN_OUTPUT_PATH, when ISSUE_API_TOKEN=true" >&2
  exit 1
fi

if [[ ! -f "${ADAPTER_SCRIPT}" ]]; then
  echo "Missing adapter script: ${ADAPTER_SCRIPT}" >&2
  exit 1
fi

echo "Waiting for OpenProject web deployment rollout"
kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" rollout status "deploy/${OPENPROJECT_DEPLOYMENT}" --timeout=300s >/dev/null

if [[ "${ISSUE_API_TOKEN}" == "true" && -n "${VAULT_SECRET_PATH}" ]]; then
  if [[ -z "${VAULT_TOKEN:-}" ]]; then
    echo "VAULT_TOKEN must be set when ISSUE_API_TOKEN=true and VAULT_SECRET_PATH is used" >&2
    exit 1
  fi
  echo "Checking Vault reachability"
  if ! vault_cmd vault status >/dev/null 2>&1; then
    echo "Vault is not reachable with the supplied VAULT_TOKEN and VAULT_ADDR" >&2
    exit 1
  fi
fi

output_file="$(mktemp)"
payload_file="$(mktemp)"
vault_output_file="$(mktemp)"
token_file=""
cleanup() {
  rm -f "${output_file}" "${payload_file}" "${vault_output_file}"
  if [[ -n "${token_file}" ]]; then
    rm -f "${token_file}"
  fi
}
trap cleanup EXIT

echo "Converging OpenProject identity ${TARGET_LOGIN}"
env \
  KUBECTL="${KUBECTL}" \
  OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE}" \
  TARGET_LOGIN="${TARGET_LOGIN}" \
  TARGET_FIRSTNAME="${TARGET_FIRSTNAME}" \
  TARGET_LASTNAME="${TARGET_LASTNAME}" \
  TARGET_MAIL="${TARGET_MAIL}" \
  TARGET_PROJECT_IDENTIFIER="${TARGET_PROJECT_IDENTIFIER}" \
  TARGET_PROJECT_IDENTIFIERS_JSON="${TARGET_PROJECT_IDENTIFIERS_JSON}" \
  TARGET_TOKEN_NAME="${TARGET_TOKEN_NAME}" \
  TARGET_ROLE_NAMES_JSON="${TARGET_ROLE_NAMES_JSON}" \
  ROTATE_API_TOKEN="${ROTATE_API_TOKEN}" \
  ISSUE_API_TOKEN="${ISSUE_API_TOKEN}" \
  TARGET_LANGUAGE="${TARGET_LANGUAGE:-}" \
  python3 "${ADAPTER_SCRIPT}" --operation provision-identity >"${output_file}"

python3 - "${output_file}" "${payload_file}" <<'PY'
from pathlib import Path
import json
import sys

start_marker = "__OPENPROJECT_IDENTITY_PROVISION_BEGIN__"
end_marker = "__OPENPROJECT_IDENTITY_PROVISION_END__"
text = Path(sys.argv[1]).read_text()
start = text.find(start_marker)
end = text.find(end_marker)
if start == -1 or end == -1 or end <= start:
    sys.stderr.write(text)
    raise SystemExit("failed to extract provisioning result payload from runner output")
payload = text[start + len(start_marker):end].strip()
data = json.loads(payload)
Path(sys.argv[2]).write_text(json.dumps(data))
PY

token_plaintext="$(python3 - "${payload_file}" <<'PY'
from pathlib import Path
import json
import sys

payload = json.loads(Path(sys.argv[1]).read_text())
print(payload["api_token"].get("plaintext_value") or "", end="")
PY
)"

if [[ "${ISSUE_API_TOKEN}" == "true" && -n "${OPENPROJECT_API_TOKEN_OUTPUT_PATH}" && -n "${token_plaintext}" ]]; then
  mkdir -p "$(dirname "${OPENPROJECT_API_TOKEN_OUTPUT_PATH}")"
  umask 077
  printf '%s' "${token_plaintext}" > "${OPENPROJECT_API_TOKEN_OUTPUT_PATH}"
fi

if [[ "${ISSUE_API_TOKEN}" == "true" && -n "${VAULT_SECRET_PATH}" && -n "${token_plaintext}" ]]; then
  echo "Writing OpenProject API token to Vault path ${VAULT_SECRET_PATH}"
  token_file="$(mktemp)"
  chmod 600 "${token_file}"
  printf '%s' "${token_plaintext}" > "${token_file}"
  kubectl_cmd -n "${VAULT_NAMESPACE}" exec -i "${VAULT_POD}" -- env \
    VAULT_ADDR="${VAULT_ADDR}" \
    VAULT_TOKEN="${VAULT_TOKEN}" \
    sh -ceu '
vault_path="$1"
tmp_secret="$(mktemp)"
cat > "${tmp_secret}"
vault kv put "${vault_path}" apiToken=@"${tmp_secret}" >/dev/null
rm -f "${tmp_secret}"
' sh "${VAULT_SECRET_PATH}" < "${token_file}"
elif [[ "${ISSUE_API_TOKEN}" == "true" && -n "${VAULT_SECRET_PATH}" ]] && ! vault_cmd vault kv get -format=json "${VAULT_SECRET_PATH}" > "${vault_output_file}" 2>/dev/null; then
  echo "OpenProject API token already exists but no plaintext value was available and Vault path ${VAULT_SECRET_PATH} is missing; rerun with ROTATE_API_TOKEN=true to rotate the token and restore Vault state" >&2
  exit 1
fi

if [[ "${ISSUE_API_TOKEN}" == "true" && -n "${OPENPROJECT_API_TOKEN_OUTPUT_PATH}" && -z "${token_plaintext}" && ! -s "${OPENPROJECT_API_TOKEN_OUTPUT_PATH}" ]]; then
  echo "OpenProject API token already exists but no plaintext value was available and ${OPENPROJECT_API_TOKEN_OUTPUT_PATH} is empty; rerun with ROTATE_API_TOKEN=true to refresh the local handoff token" >&2
  exit 1
fi

if [[ "${ISSUE_API_TOKEN}" == "true" && -n "${VAULT_SECRET_PATH}" ]]; then
  vault_cmd vault kv get -format=json "${VAULT_SECRET_PATH}" > "${vault_output_file}"
  vault_keys="$(python3 - "${vault_output_file}" <<'PY'
from pathlib import Path
import json
import sys

payload = json.loads(Path(sys.argv[1]).read_text())
print(", ".join(sorted(payload["data"]["data"].keys())))
PY
)"
else
  vault_keys=""
fi

python3 - "${payload_file}" "${VAULT_SECRET_PATH}" "${vault_keys}" "${OPENPROJECT_API_TOKEN_OUTPUT_PATH}" <<'PY'
from pathlib import Path
import json
import sys

payload = json.loads(Path(sys.argv[1]).read_text())
payload["api_token"].pop("plaintext_value", None)
if sys.argv[4]:
    payload["api_token"]["output_path"] = sys.argv[4]
if payload["api_token"].get("enabled"):
    payload["vault"] = {
        "secret_path": sys.argv[2],
        "stored_keys": sys.argv[3].split(", ") if sys.argv[3] else [],
    }
print("__OPENPROJECT_IDENTITY_PROVISION_BEGIN__")
print(json.dumps(payload, indent=2))
print("__OPENPROJECT_IDENTITY_PROVISION_END__")
PY
