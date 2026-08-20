#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

write_status_file

cat >"${PROFILE_PROMOTION_NOTES}" <<'EOF'
# Governed AI Gateway Dev-Integration Promotion Notes

This local profile does not promote directly to stage.

Stage handoff requires:

- active dev-integration profile admission
- gateway API readiness
- caller identity boundary
- provider credential custody
- audit ledger emission
- gateway-only consumer egress proof
- direct-provider sentinel denial
- direct Ollama denial from governed consumers
- pinned Ollama version and model digest
- strict provider output and bounded failure handling
- current security delta review

The platform model profile and local binding may remain active in
dev-integration. Workspace consumer activation and any stage or production
route remain separately gated.
EOF

cat "${PROFILE_PROMOTION_NOTES}"

if [[ -f "${PROMOTION_REPORT}" ]]; then
  printf '\nShared runner promotion report:\n'
  cat "${PROMOTION_REPORT}"
fi
