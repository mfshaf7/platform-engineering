# Change Record

## Summary

- Date: 2026-04-03
- Short title: Ollama portproxy drift recovery
- Environment: prod host/runtime
- Severity: high

## Classification

- Type: host/environment drift
- User-facing impact: non-host-control Telegram topics routed to the correct agents but failed during inference with `fetch failed`.

## Ownership

- Owning repo or layer: host/runtime environment
- Related repos: `platform-engineering`

## Root Cause

- Immediate failure: the prod gateway pod could not reach `http://host.docker.internal:11434/api/tags`.
- Actual root cause: the Windows portproxy for the WSL-resolved `host.docker.internal` address had drifted even though local Windows Ollama on `127.0.0.1:11434` was healthy.
- Why it escaped earlier controls: there was no active evidence record or recovery runbook for the Ollama forward path at incident time.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): `8f2855b9de3499d2ad5af28bf05dd0545156699d`
- Guardrail added:
  - `docs/runbooks/host-runtime-drift-recovery.md`

## Artifact And Deployment Evidence

- Build workflow run: None
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: not applicable

## Host Or Runtime Recovery

- Required host/runtime action: refresh Windows portproxy for the WSL-resolved `host.docker.internal` listen address
- Why it was environment drift instead of source defect: the gateway image and Telegram routing were already correct; only the host-side forward path was broken
- Recovery command or procedure:
  - delete and recreate the `11434` portproxy for the current `host.docker.internal` address to `127.0.0.1:11434`

## Live Verification

- App health: gateway app remained healthy
- Deployed image: existing prod image continued to run
- Pod: gateway pod could reach `http://host.docker.internal:11434/api/tags` after the repair
- Functional verification: `security-architecture` topic responded again once model reachability was restored
- Residual risk: this can recur if Windows network/interface state changes and the portproxy is not refreshed

## Follow-Up

- Required follow-up: keep this recovery path in the host/runtime drift runbook
- Optional hardening: add a periodic health check for Ollama reachability from the gateway path
- Owner: platform engineering / host operations
