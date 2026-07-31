#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

ensure_state_dir
cat >"${PROFILE_PROMOTION_NOTES}" <<'EOF'
# Temporal Dev-Integration Promotion Notes

Promotion is blocked while the profile is proposed.

Required before stage handoff:

- active dev-integration profile admission
- OOS Temporal adapter and workflow definition contract
- namespace and task queue identity boundary
- PostgreSQL persistence migration backup and restore
- worker and runtime restart replay proof
- workflow and activity idempotency retry timeout and cancellation
- observability retention and payload redaction
- current security acceptance
- source projection rollback and suspension proof
EOF
cat "${PROFILE_PROMOTION_NOTES}"
exit 2
