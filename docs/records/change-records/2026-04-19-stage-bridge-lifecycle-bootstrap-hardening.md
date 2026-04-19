---
security_evidence:
  review_areas:
    - runtime
    - delivery
  findings:
    - F-019
  risks:
    - R-019
  workstreams:
    - WS-019
---

# Change Record

## Summary

- Date: 2026-04-19
- Short title: Harden the stage bridge lifecycle path around the supported Windows-to-WSL bootstrap model
- Environment: OpenClaw stage lifecycle and WSL host bootstrap
- Severity: High

## Classification

- Type:
  - host/environment drift
- User-facing impact: The primary stage lifecycle script and bootstrap docs now align on the supported `systemd` path instead of leaving operators to rediscover the Windows-to-WSL root bootstrap behavior or legacy tmux artifacts.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos:
  - `openclaw-host-bridge`
  - `openclaw-telegram-enhanced`
- Related ADR: None

## Root Cause

- Immediate failure: `set_stage_environment_state.py` stalled on interactive `sudo`, and the bootstrap docs still treated a legacy tmux launcher as a provisioning prerequisite.
- Actual root cause: the supported non-interactive root path existed in the Windows bootstrap artifact, but the stage lifecycle script, bootstrap runbook, and WSL host defaults were not describing or validating the same model.
- Why it escaped earlier controls: operational-doc validation covered workflow headings and freshness stamps, but it did not check the supported WSL bootstrap contract itself.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): Local worktree only
- Guardrail added:
  - test: None
  - validator: `scripts/validate_operational_docs.py` now checks that WSL bootstrap docs and defaults do not require the legacy tmux stack path
  - runbook: `docs/runbooks/bootstrap-wsl-distro.md` now points at the supervisor-based prerequisites
  - ADR: None

## Artifact And Deployment Evidence

- Build workflow run: None
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: None
- Why it was environment drift instead of source defect: The live outage was recovered earlier; this change repairs the source-owned lifecycle and bootstrap doctrine so the supported recovery path is available without ad hoc operator rediscovery.
- Recovery command or procedure: `python3 products/openclaw/scripts/set_stage_environment_state.py resume --components gateway,version`

If not applicable, write `None`.

## Live Verification

- App health: `python3 products/openclaw/scripts/set_stage_environment_state.py status --repo-root /home/mfshaf7/projects/platform-engineering` returned `active:gateway,secrets,version`
- Deployed image: None
- Pod: None
- Functional verification: `python3 scripts/validate_operational_docs.py --repo-root .` passed after the bootstrap-contract validator was added.
- Residual risk: The governed stage lifecycle still depends on cross-repo recovery behavior, so the platform, bridge, and Telegram changes should land together.

## Follow-Up

- Required follow-up: Keep the stage operator surface anchored on `set_stage_environment_state.py` and avoid reintroducing legacy launchers into supported bootstrap docs.
- Optional hardening: Add a product-level smoke that exercises the recovery selector with stage-targeted payloads after the cross-repo change lands.
- Owner: `platform-engineering`
