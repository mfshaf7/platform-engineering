# Change Record

## Summary

- Date: 2026-04-17
- Short title: Stage Telegram native-command contract for `/platform`
- Environment: stage
- Severity: medium

## Classification

- Type: host/environment drift
- User-facing impact: the staged `/platform` operator command fell through to the embedded agent path and replied with an error instead of the deterministic native handler.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `openclaw-telegram-enhanced`, `security-architecture`

## Root Cause

- Immediate failure: the stage gateway runtime did not register Telegram native commands, so `/platform` was never intercepted by the Telegram-native command layer.
- Actual root cause: the host-managed stage OpenClaw config at `~/.openclaw-stage/openclaw.stage.k3s.json` omitted `channels.telegram.commands.native: true`, and the existing stage lifecycle checks only validated bridge wiring.
- Why it escaped earlier controls: the platform guardrails did not validate the local stage OpenClaw config beyond `bridgeUrl`, and the host-managed stage config lives outside Git.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): Pending local platform-engineering change
- Guardrail added:
  - validator in `products/openclaw/scripts/set_stage_environment_state.py`
  - runbook updates in `products/openclaw/runbooks/access-openclaw.md`
  - host-bootstrap/runbook updates in `docs/runbooks/bootstrap-wsl-distro.md` and `docs/runbooks/host-stack-rollout.md`

## Artifact And Deployment Evidence

- Build workflow run: existing staged gateway candidate; no rebuild required
- Published image tag: `stage-1fb1b11b4142`
- Published digest: `sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`
- Recorded prod revision: None
- Argo application revision: stage `openclaw-gateway-stage` after rollout restart on the active stage contract

## Host Or Runtime Recovery

- Required host/runtime action: update `~/.openclaw-stage/openclaw.stage.k3s.json` to set `channels.telegram.commands.native: true` and restart the stage gateway deployment
- Why it was environment drift instead of source defect: the `/platform` command source and staged image already contained the feature; the failure was in the host-managed runtime config consumed by the stage gateway
- Recovery command or procedure: repair the local stage config, then `k3s kubectl -n openclaw-stage rollout restart deploy/openclaw-gateway`

## Live Verification

- App health: stage deployment rolled out successfully after restart
- Deployed image: `ghcr.io/mfshaf7/openclaw-gateway@sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`
- Pod: `openclaw-gateway-7474fb69b8-j4xlj`
- Functional verification: stage bot now publishes `/platform` in Telegram `getMyCommands`; manual inbound operator verification is still required to complete the acceptance pack
- Residual risk: end-to-end reply handling still needs a real operator-issued Telegram command, and broader host-control rehearsal remains blocked until stage bridge reachability is restored

## Follow-Up

- Required follow-up: run the `/platform` operator manual acceptance pack and update stage verification evidence from `blocked` once real inbound testing completes
- Optional hardening: model more host-managed OpenClaw runtime prerequisites as explicit local validation checks before stage rehearsal
- Owner: platform engineering
