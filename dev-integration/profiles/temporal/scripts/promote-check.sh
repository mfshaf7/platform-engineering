#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

write_status_file
cat >"${PROFILE_PROMOTION_NOTES}" <<EOF
# Temporal Dev-Integration Promotion Notes

This local profile does not promote its runtime directly to stage.

Current profile lifecycle: ${PROFILE_LIFECYCLE}

Stage handoff requires:

- active dev-integration profile admission
- OOS Temporal adapter and workflow definition contract
- namespace and task queue identity boundary
- PostgreSQL persistence migration backup and restore
- worker and runtime restart replay proof
- workflow and activity idempotency retry timeout and cancellation
- observability retention and payload redaction
- current security acceptance
- source projection rollback and suspension proof

Source implementation is defined, but runtime proof and fresh Security
acceptance remain separate gates.
EOF
cat "${PROFILE_PROMOTION_NOTES}"

if [[ -f "${PROMOTION_REPORT}" ]]; then
  printf '\nShared runner promotion report:\n'
  cat "${PROMOTION_REPORT}"
fi

if ! is_active_profile; then
  exit 2
fi

if [[ ! -f "${SMOKE_SUMMARY}" ]] \
  || ! grep -q '"result": "passed"' "${SMOKE_SUMMARY}"; then
  printf '\nblocked: read-only Temporal smoke evidence is missing or not passing\n' >&2
  exit 2
fi

printf '\nblocked: durability, backup/restore, correlated receipt, and fresh Security evidence remain required\n' >&2
exit 2
