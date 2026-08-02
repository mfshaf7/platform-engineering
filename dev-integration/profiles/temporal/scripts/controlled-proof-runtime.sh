#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

readonly ACTION="${1:-}"

refuse() {
  printf 'refused: %s\n' "$1" >&2
  exit 2
}

require_controlled_executor() {
  [[ "$#" == "1" ]] || refuse "controlled proof runtime accepts one fixed action"
  [[ "${CONTROLLED_PROOF_EXECUTOR:-}" == "true" ]] || \
    refuse "controlled proof runtime is available only to the permit-bound executor"
  [[ "${PROFILE_LIFECYCLE}" == "build-admitted" ]] || \
    refuse "controlled proof runtime requires the build-admitted profile"
  [[ "${CONTROLLED_PROOF_AUTHORIZATION_ID:-}" =~ ^[a-z][a-z0-9+.-]*://[^[:space:]]+$ ]] || \
    refuse "controlled proof authorization id is missing or malformed"
  [[ "${CONTROLLED_PROOF_CONSUMPTION_RECEIPT_DIGEST:-}" =~ ^sha256:[0-9a-f]{64}$ ]] || \
    refuse "controlled proof consumption receipt digest is missing or malformed"
  [[ "${CONTROLLED_PROOF_EXECUTOR_SOURCE_REVISION:-}" =~ ^[0-9a-f]{40}$ ]] || \
    refuse "controlled proof executor source revision is missing or malformed"
}

require_runtime_state() {
  local expected="$1"
  local actual
  actual="$(runtime_state)"
  [[ "${actual}" == "${expected}" ]] || \
    refuse "controlled proof runtime must be ${expected}, got ${actual}"
}

prepare_runtime() {
  need_cmd helm
  need_cmd k3s
  need_cmd python3
  need_cmd sha256sum
  require_runtime_state "not-installed"
  [[ ! -e "${STATE_ROOT}" ]] || \
    refuse "controlled proof baseline requires absent operator-local state"

  render_runtime
  ensure_chart
  kubectl_cmd create namespace "${NAMESPACE}" --dry-run=client -o yaml | \
    kubectl_cmd apply -f -
  kubectl_cmd label namespace "${NAMESPACE}" \
    app.kubernetes.io/part-of=temporal \
    dev-integration-profile=temporal \
    "dev-integration-operator=${OPERATOR_SLUG}" \
    controlled-proof-session=true \
    --overwrite
  apply_database_secret
  kubectl_cmd apply -f "${RENDERED_DIR}/postgresql.yaml"
  kubectl_cmd apply -f "${RENDERED_DIR}/network-boundaries.yaml"
  wait_for_postgresql

  helm upgrade --install "${RELEASE_NAME}" "${CHART_ARCHIVE}" \
    --namespace "${NAMESPACE}" \
    --values "${RENDERED_DIR}/temporal-values.yaml" \
    --atomic \
    --timeout 10m \
    --wait
  wait_for_runtime_ready
  require_runtime_state "running"
}

restart_temporal() {
  need_cmd k3s
  require_runtime_state "running"
  scale_temporal_deployments 0
  wait_for_temporal_deployments_suspended
  scale_temporal_deployments 1
  wait_for_runtime_ready
  require_runtime_state "running"
}

backup_restore() {
  need_cmd k3s
  need_cmd sha256sum
  require_runtime_state "running"

  scale_temporal_deployments 0
  wait_for_temporal_deployments_suspended
  restore_runtime_after_failure() {
    scale_temporal_deployments 1 || true
    wait_for_runtime_ready || true
  }
  trap restore_runtime_after_failure EXIT

  local backup_path
  backup_path="${BACKUPS_DIR}/controlled-proof-${CONTROLLED_PROOF_CONSUMPTION_RECEIPT_DIGEST#sha256:}.sql"
  backup_database "${backup_path}" >/dev/null
  kubectl_cmd -n "${NAMESPACE}" exec -i \
    "statefulset/${POSTGRESQL_STATEFULSET}" -- \
    sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres' \
    <"${backup_path}"

  scale_temporal_deployments 1
  wait_for_runtime_ready
  trap - EXIT
  require_runtime_state "running"
}

remove_scoped_runtime() {
  need_cmd k3s
  assert_state_root_boundary
  kubectl_cmd delete namespace "${NAMESPACE}" --ignore-not-found=true --wait=true
  rm -rf "${STATE_ROOT}"
  require_runtime_state "not-installed"
}

require_controlled_executor "$@"

case "${ACTION}" in
  prepare)
    prepare_runtime
    ;;
  restart-temporal)
    restart_temporal
    ;;
  backup-restore)
    backup_restore
    ;;
  restore-baseline|cleanup)
    remove_scoped_runtime
    ;;
  *)
    refuse "unsupported controlled proof runtime action"
    ;;
esac
