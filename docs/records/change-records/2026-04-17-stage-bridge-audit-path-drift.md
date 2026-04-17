---
security_evidence:
  review_areas:
    - runtime
  findings:
    - F-006
  risks:
    - R-006
  workstreams:
    - WS-006
---

# Change Record

## Summary

- Date: 2026-04-17
- Short title: Stage bridge audit-path drift blocked live host-control rehearsal
- Environment: stage
- Severity: medium

## Classification

- Type: host/environment drift
- User-facing impact: the staged host-control bridge answered `/healthz` but
  crashed on the first real `/v1/bridge` request, so privileged-path rehearsal
  could not complete.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `openclaw-host-bridge`

## Root Cause

- Immediate failure: the local stage audit directory under
  `~/.openclaw-stage/logs/openclaw-host-audit/` was owned by a different user,
  so audited bridge requests failed with `EACCES`.
- Actual root cause: the stage lifecycle checks only validated
  `systemctl is-active` plus bridge `/healthz`, which did not prove that the
  audited request path could write to the host-side audit log.
- Why it escaped earlier controls: `/healthz` returns runtime identity and
  policy alignment, but it does not exercise the authenticated bridge request
  path or audit append.

## Source Changes

- Repo: `platform-engineering`
- Guardrail added:
  - `products/openclaw/scripts/set_stage_environment_state.py` now probes one
    authenticated read-only bridge request before it considers the stage bridge
    ready.
  - `products/openclaw/runbooks/access-openclaw.md` now documents that the
    local audit path must be writable for stage resume to succeed.

## Artifact And Deployment Evidence

- Build workflow run: none; existing stage candidate remained under test
- Published image tag: `stage-1fb1b11b4142`
- Published digest:
  `sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`
- Recorded prod revision: none
- Argo application revision: unchanged for this guardrail; the active stage
  candidate remained `1fb1b11b4142`

## Host Or Runtime Recovery

- Required host/runtime action: rotate the stale audit directory aside and
  recreate `~/.openclaw-stage/logs/openclaw-host-audit/` as a writable
  user-owned directory.
- Why it was environment drift instead of source defect: the live bridge code
  and stage gateway contract were correct; only the host-side audit path
  ownership had drifted.

## Live Verification

- App health: stage bridge `/healthz` returned `ok=true` after restart.
- Functional verification: authenticated bridge requests for
  `config.allowed_roots.list`, `config.allowed_roots.add`, and
  `config.allowed_roots.remove` all returned `ok=true`.
- Host evidence:
  - audit file:
    `~/.openclaw-stage/logs/openclaw-host-audit/2026-04-16.jsonl`
  - audit ids:
    `5b05bf28-64f1-4e19-9616-bf289b38fd78`,
    `f40813a2-6b79-4a12-baa6-71d62b71ffba`,
    `cec823b0-f8d9-4bc1-91a5-6e4bba5fba55`,
    `8bd5c6bf-39c8-4b68-9854-4cbb4be6c01b`,
    `4c380935-66bc-4847-b3cf-2b6a4b78ea37`
- Residual risk: stage still requires the remaining Telegram reply, file
  delivery, and screenshot-delivery checks before promotion readiness can be
  approved.

## Follow-Up

- Required follow-up: keep the local stage audit directory under the active
  `~/.openclaw-stage` home root and preserve writability when rotating or
  restoring host logs.
- Optional hardening: surface audit-path writability directly in the bridge
  health output so local operators can see the failure without forcing a live
  request first.
- Owner: platform engineering
