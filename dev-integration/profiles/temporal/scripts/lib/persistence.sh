# shellcheck shell=bash

assert_state_root_boundary() {
  python3 - "${STATE_ROOT}" "${OWNER_REPO_ROOT}" \
    "${DEVINT_WORKSPACE_ROOT:-}" "${PROFILE_ID}" \
    "${CONTROLLED_PROOF_OPERATOR_SCOPE:-${OPERATOR_SLUG}}" <<'PY'
import pathlib
import sys

state_root = pathlib.Path(sys.argv[1]).resolve()
profile_id = sys.argv[4]
operator_scope = sys.argv[5]
allowed_profile_roots = [
    pathlib.Path(sys.argv[2]).resolve() / ".dev-integration" / profile_id,
]
if sys.argv[3]:
    allowed_profile_roots.append(
        pathlib.Path(sys.argv[3]).resolve() / ".dev-integration" / profile_id
    )

if state_root.name != operator_scope:
    raise SystemExit("refused: Temporal state root does not match the operator scope")
if not any(root.resolve() in state_root.parents for root in allowed_profile_roots):
    raise SystemExit("refused: Temporal state root is outside an approved profile root")
PY
}

ensure_local_secrets() {
  ensure_state_dirs
  if [[ ! -f "${LOCAL_SECRETS_ENV}" ]]; then
    umask 077
    python3 - "${LOCAL_SECRETS_ENV}" <<'PY'
import pathlib
import secrets
import sys

path = pathlib.Path(sys.argv[1])
path.write_text(
    "TEMPORAL_POSTGRES_ADMIN_USERNAME=temporal_admin\n"
    f"TEMPORAL_POSTGRES_ADMIN_PASSWORD={secrets.token_hex(32)}\n"
    "TEMPORAL_POSTGRES_USERNAME=temporal\n"
    f"TEMPORAL_POSTGRES_PASSWORD={secrets.token_hex(32)}\n",
    encoding="utf-8",
)
path.chmod(0o600)
PY
  fi
  if [[ "$(stat -c '%a' "${LOCAL_SECRETS_ENV}")" != "600" ]]; then
    printf 'refused: operator-local PostgreSQL credential file must use mode 0600\n' >&2
    exit 1
  fi

  TEMPORAL_POSTGRES_ADMIN_USERNAME=""
  TEMPORAL_POSTGRES_ADMIN_PASSWORD=""
  TEMPORAL_POSTGRES_USERNAME=""
  TEMPORAL_POSTGRES_PASSWORD=""
  local key
  local value
  while IFS='=' read -r key value; do
    case "${key}" in
      TEMPORAL_POSTGRES_ADMIN_USERNAME)
        TEMPORAL_POSTGRES_ADMIN_USERNAME="${value}"
        ;;
      TEMPORAL_POSTGRES_ADMIN_PASSWORD)
        TEMPORAL_POSTGRES_ADMIN_PASSWORD="${value}"
        ;;
      TEMPORAL_POSTGRES_USERNAME)
        TEMPORAL_POSTGRES_USERNAME="${value}"
        ;;
      TEMPORAL_POSTGRES_PASSWORD)
        TEMPORAL_POSTGRES_PASSWORD="${value}"
        ;;
      "")
        ;;
      *)
        printf 'refused: unexpected key in operator-local PostgreSQL credential file\n' >&2
        exit 1
        ;;
    esac
  done <"${LOCAL_SECRETS_ENV}"

  if [[ ! "${TEMPORAL_POSTGRES_ADMIN_USERNAME:-}" =~ ^[a-z_][a-z0-9_]*$ \
    || ! "${TEMPORAL_POSTGRES_USERNAME:-}" =~ ^[a-z_][a-z0-9_]*$ \
    || ! "${TEMPORAL_POSTGRES_ADMIN_PASSWORD:-}" =~ ^[0-9a-f]{64}$ \
    || ! "${TEMPORAL_POSTGRES_PASSWORD:-}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'refused: operator-local PostgreSQL credential file is malformed\n' >&2
    exit 1
  fi
  export \
    TEMPORAL_POSTGRES_ADMIN_USERNAME \
    TEMPORAL_POSTGRES_ADMIN_PASSWORD \
    TEMPORAL_POSTGRES_USERNAME \
    TEMPORAL_POSTGRES_PASSWORD
}

apply_database_secret() {
  ensure_local_secrets
  python3 - "${NAMESPACE}" "${POSTGRESQL_SECRET}" <<'PY' | kubectl_cmd apply -f -
import json
import os
import sys

payload = {
    "apiVersion": "v1",
    "kind": "Secret",
    "metadata": {
        "name": sys.argv[2],
        "namespace": sys.argv[1],
        "labels": {"app.kubernetes.io/part-of": "temporal"},
    },
    "type": "Opaque",
    "stringData": {
        "admin_username": os.environ["TEMPORAL_POSTGRES_ADMIN_USERNAME"],
        "admin_password": os.environ["TEMPORAL_POSTGRES_ADMIN_PASSWORD"],
        "username": os.environ["TEMPORAL_POSTGRES_USERNAME"],
        "password": os.environ["TEMPORAL_POSTGRES_PASSWORD"],
    },
}
print(json.dumps(payload))
PY
}

assert_operator_file_path() {
  local candidate="$1"
  python3 - "${candidate}" "${STATE_ROOT}" "${ARCHIVE_ROOT}" <<'PY'
import pathlib
import sys

candidate = pathlib.Path(sys.argv[1]).resolve()
allowed_roots = [pathlib.Path(value).resolve() for value in sys.argv[2:]]
if not any(root in candidate.parents for root in allowed_roots):
    raise SystemExit(
        "refused: Temporal evidence path is outside the operator state and archive roots"
    )
PY
}

backup_database() {
  local destination="$1"
  assert_operator_file_path "${destination}"
  if [[ -e "${destination}" || -e "${destination}.manifest.json" ]]; then
    printf 'refused: Temporal backup destination already exists: %s\n' \
      "${destination}" >&2
    exit 2
  fi
  mkdir -p "$(dirname "${destination}")"
  umask 077
  kubectl_cmd -n "${NAMESPACE}" exec "statefulset/${POSTGRESQL_STATEFULSET}" -- \
    sh -ec '
      export PGPASSWORD="$POSTGRES_PASSWORD"
      for database in temporal temporal_visibility; do
        printf "\n-- Temporal dev-integration database: %s\n" "$database"
        pg_dump --clean --if-exists --create \
          --username "$POSTGRES_USER" "$database"
      done
    ' \
    >"${destination}"
  chmod 600 "${destination}"

  local digest
  digest="$(sha256sum "${destination}" | awk '{print $1}')"
  python3 - "${destination}.manifest.json" "${destination}" "${digest}" \
    "${NAMESPACE}" "${TEMPORAL_WORKFLOW_NAMESPACE}" <<'PY'
from datetime import datetime, timezone
import json
import pathlib
import sys

payload = {
    "schema_version": 1,
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "backup_path": sys.argv[2],
    "sha256": sys.argv[3],
    "kubernetes_namespace": sys.argv[4],
    "temporal_namespace": sys.argv[5],
    "contains_workflow_history": True,
    "databases": ["temporal", "temporal_visibility"],
    "role_passwords_included": False,
    "custody": "operator-local",
}
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
  printf '%s\n' "${destination}"
}
