#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

ensure_state_dir
cat >"${SMOKE_SUMMARY}" <<EOF
{
  "profile": "${PROFILE_ID}",
  "lifecycle": "${PROFILE_LIFECYCLE}",
  "runtime_launchable": false,
  "smoke_mode": "read-only",
  "result": "blocked-until-build-admitted-and-active"
}
EOF
cat "${SMOKE_SUMMARY}"
exit 2
