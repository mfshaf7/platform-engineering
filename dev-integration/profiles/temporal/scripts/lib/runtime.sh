# shellcheck shell=bash

runtime_state() {
  if ! command -v k3s >/dev/null 2>&1; then
    printf 'cluster-client-unavailable'
    return
  fi
  local namespace_result
  if ! namespace_result="$(kubectl_cmd get namespace "${NAMESPACE}" -o name 2>&1)"; then
    if [[ "${namespace_result}" == *"NotFound"* \
      || "${namespace_result}" == *"not found"* ]]; then
      printf 'not-installed'
    else
      printf 'cluster-query-failed'
    fi
    return
  fi

  local postgresql_desired
  local postgresql_ready
  local postgresql_current
  postgresql_desired="$(
    kubectl_cmd -n "${NAMESPACE}" get statefulset "${POSTGRESQL_STATEFULSET}" \
      -o jsonpath='{.spec.replicas}' 2>/dev/null || true
  )"
  postgresql_ready="$(
    kubectl_cmd -n "${NAMESPACE}" get statefulset "${POSTGRESQL_STATEFULSET}" \
      -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true
  )"
  postgresql_current="$(
    kubectl_cmd -n "${NAMESPACE}" get statefulset "${POSTGRESQL_STATEFULSET}" \
      -o jsonpath='{.status.currentReplicas}' 2>/dev/null || true
  )"

  local all_running=1
  local all_suspended=1
  local deployment
  local desired
  local available
  local current
  for deployment in "${TEMPORAL_DEPLOYMENTS[@]}"; do
    desired="$(
      kubectl_cmd -n "${NAMESPACE}" get deployment "${deployment}" \
        -o jsonpath='{.spec.replicas}' 2>/dev/null || true
    )"
    available="$(
      kubectl_cmd -n "${NAMESPACE}" get deployment "${deployment}" \
        -o jsonpath='{.status.availableReplicas}' 2>/dev/null || true
    )"
    current="$(
      kubectl_cmd -n "${NAMESPACE}" get deployment "${deployment}" \
        -o jsonpath='{.status.replicas}' 2>/dev/null || true
    )"
    if [[ "${desired}" != "1" || "${available:-0}" != "1" ]]; then
      all_running=0
    fi
    if [[ "${desired}" != "0" || "${current:-0}" != "0" ]]; then
      all_suspended=0
    fi
  done

  if [[ "${all_running}" == "1" \
    && "${postgresql_desired}" == "1" \
    && "${postgresql_ready:-0}" == "1" ]]; then
    printf 'running'
    return
  fi
  if [[ "${all_suspended}" == "1" \
    && "${postgresql_desired}" == "0" \
    && "${postgresql_current:-0}" == "0" ]]; then
    printf 'suspended'
    return
  fi
  printf 'installed-not-ready'
}

render_runtime() {
  ensure_state_dirs
  python3 "${PROFILE_ROOT}/scripts/render_runtime.py" \
    --profile-root "${PROFILE_ROOT}" \
    --output-dir "${RENDERED_DIR}" \
    --namespace "${NAMESPACE}" \
    --operator-scope "${CONTROLLED_PROOF_OPERATOR_SCOPE:-${OPERATOR_SLUG}}" \
    --temporal-namespace "${TEMPORAL_WORKFLOW_NAMESPACE}"
}

ensure_chart() {
  ensure_state_dirs
  if [[ ! -f "${CHART_ARCHIVE}" ]]; then
    helm pull "${CHART_NAME}" \
      --repo "${CHART_REPOSITORY}" \
      --version "${CHART_VERSION}" \
      --destination "${ARTIFACTS_DIR}"
  fi

  local actual
  actual="$(sha256sum "${CHART_ARCHIVE}" | awk '{print $1}')"
  if [[ "${actual}" != "${CHART_SHA256}" ]]; then
    rm -f "${CHART_ARCHIVE}"
    printf 'Temporal chart checksum mismatch: expected %s, got %s\n' \
      "${CHART_SHA256}" "${actual}" >&2
    exit 1
  fi
}

wait_for_postgresql() {
  kubectl_cmd -n "${NAMESPACE}" rollout status \
    "statefulset/${POSTGRESQL_STATEFULSET}" --timeout=300s
}

wait_for_runtime_ready() {
  wait_for_postgresql
  local deployment
  for deployment in "${TEMPORAL_DEPLOYMENTS[@]}"; do
    kubectl_cmd -n "${NAMESPACE}" rollout status \
      "deployment/${deployment}" --timeout=600s
  done
}

scale_temporal_deployments() {
  local replicas="$1"
  local deployment
  for deployment in "${TEMPORAL_DEPLOYMENTS[@]}"; do
    kubectl_cmd -n "${NAMESPACE}" scale "deployment/${deployment}" \
      --replicas="${replicas}" >/dev/null 2>&1 || true
  done
}

wait_for_zero_replicas() {
  local resource="$1"
  local current
  local attempt
  for ((attempt = 1; attempt <= 150; attempt++)); do
    current="$(
      kubectl_cmd -n "${NAMESPACE}" get "${resource}" \
        -o jsonpath='{.status.replicas}' 2>/dev/null || true
    )"
    if [[ "${current:-0}" == "0" ]]; then
      return
    fi
    sleep 2
  done
  printf 'Timed out waiting for %s to reach zero replicas\n' "${resource}" >&2
  return 1
}

wait_for_temporal_deployments_suspended() {
  local deployment
  for deployment in "${TEMPORAL_DEPLOYMENTS[@]}"; do
    wait_for_zero_replicas "deployment/${deployment}"
  done
}
