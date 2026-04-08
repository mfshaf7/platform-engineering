# Change Record

## Summary

- Date: 2026-04-08
- Short title: Retire legacy Windows OpenClaw startup helpers after reboot validation
- Environment: local Windows + WSL `Platform-Core`
- Severity: low

## Classification

- Type:
  - host/environment drift
- User-facing impact:
  - removes stale Windows startup helpers that were no longer part of the supported bootstrap path

## Ownership

- Owning repo or layer: platform engineering / host runtime
- Related repos:
  - `platform-engineering`
  - `openclaw-host-bridge`
  - `openclaw-isolated-deployment`

## Root Cause

- Immediate failure:
  - the old `OpenClawRecovery` Windows Run entry pointed at a stale Docker-era recovery loop
- Actual root cause:
  - migration to `PlatformCoreHostStack` completed, but legacy Windows helper scripts and repo references were left behind as drift
- Why it escaped earlier controls:
  - earlier cutover work prioritized additive rollback safety before one real reboot/logon validation proved the new startup path

## Source Changes

- Repo:
  - `openclaw-host-bridge`
  - `platform-engineering`
  - `openclaw-isolated-deployment`
- Commit(s):
  - pending local workspace changes
- Guardrail added:
  - runbook
  - change record

## Artifact And Deployment Evidence

- Build workflow run: None
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action:
  - remove stale Windows recovery helper files under `C:\Users\Sevensoul\.openclaw`
- Why it was environment drift instead of source defect:
  - the active bootstrap owner was already `PlatformCoreHostStack`; the old helpers were leftover local startup artifacts
- Recovery command or procedure:
  - remove the retired Windows recovery helper scripts after confirming no scheduled task or Run entry still referenced them

## Live Verification

- App health:
  - `http://127.0.0.1:48721/healthz` returned `200`
  - `http://127.0.0.1:48722/healthz` returned `200`
- Deployed image:
  - unchanged
- Pod:
  - `openclaw/openclaw-gateway`
- Functional verification:
  - `PlatformCoreHostStack` last run succeeded on 2026-04-08
  - `openclaw-host-stack.target`, `openclaw-host-bridge.service`, and `openclaw-host-recovery.service` were active after reboot
  - authenticated `POST /v1/self-heal` with `recheck_health` succeeded after reboot
  - topic 35 Telegram `host status` and `self heal` replies were observed after reboot
- Residual risk:
  - tmux fallback scripts remain because bridge self-heal still uses the tmux bridge launcher for targeted restart

## Follow-Up

- Required follow-up:
  - keep using `make verify-restart-survival` after future bootstrap-path changes
- Optional hardening:
  - add a deterministic post-reboot verifier for Telegram topic 35 that records audit evidence on the same day
- Owner:
  - platform engineering
