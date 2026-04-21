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

- Date: 2026-04-21
- Short title: Keep stage bridge persistent while stage is active and make stage status bridge-aware
- Environment: OpenClaw stage lifecycle and host bridge
- Severity: High

## Classification

- Type:
  - host/environment drift
  - workflow hardening
- User-facing impact: stage could report `active` while Telegram
  host-control requests were already failing because the stage bridge was not
  running after host restart. The supported stage lifecycle surface now keeps
  the stage bridge persistent while stage intentionally stays active and marks
  status degraded when the bridge path is missing.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos:
  - `openclaw-host-bridge`
  - `openclaw-telegram-enhanced`

## Root Cause

- Immediate failure: the stage gateway remained healthy in Kubernetes, but the
  host-side bridge at `172.27.88.8:48731` refused connections.
- Actual root cause: stage lifecycle truth was split. The Git-managed stage
  component set still showed `gateway,secrets,version` as active, but the
  stage host bridge is an on-demand disabled-by-default `systemd` unit and did
  not come back automatically after host restart.
- Why it escaped earlier controls: `set_stage_environment_state.py status`
  only reported Git-managed stage components, not bridge request-path
  readiness, so stage could appear active while the real host-control path was
  dead.

## Source Changes

- Repo: `platform-engineering`
- Guardrail added:
  - `products/openclaw/scripts/set_stage_environment_state.py`
    - resume now enables and starts the stage bridge service before proving
      readiness
    - suspend now stops and disables the stage bridge service again
    - status now checks bridge request-path readiness and exits non-zero when
      active stage has a degraded bridge or suspended stage leaves the bridge
      unexpectedly active
  - OpenClaw runbooks and operator docs now describe the new persistence and
    bridge-aware status rule

## Artifact And Deployment Evidence

- Build workflow run: none
- Published image tag: none
- Published digest: none
- Recorded prod revision: none
- Argo application revision: unchanged for this control; stage gateway already
  remained on the active shared platform revision

## Host Or Runtime Recovery

- Required host/runtime action: run
  `python3 products/openclaw/scripts/set_stage_environment_state.py resume --components gateway,version`
  once after landing the change when stage is intentionally being kept active.
- Why it was environment drift instead of source defect: the stage gateway
  contract and Telegram path were already correct; the missing control was the
  lifecycle coupling between active stage intent and host-bridge persistence
  across host restart.

## Live Verification

- App health:
  - `k3s kubectl -n openclaw-stage exec deploy/openclaw-gateway -- wget -qO- http://127.0.0.1:18789/healthz`
    returned `{"ok":true,"status":"live"}`
  - `k3s kubectl -n openclaw-stage exec deploy/openclaw-gateway -- wget -qO- http://127.0.0.1:18789/readyz`
    returned `{"ready":true,...}`
- Bridge verification:
  - `python3 products/openclaw/scripts/set_stage_environment_state.py resume --components gateway,version`
    reported `stage_bridge=openclaw-host-bridge-stage.service:active`
  - `k3s kubectl -n openclaw-stage exec deploy/openclaw-gateway -- wget -qO- http://172.27.88.8:48731/healthz`
    returned `ok=true`
  - authenticated bridge request for `config.allowed_roots.list` returned
    `ok=true` with a real audit id
- Functional verification:
  - the previous Telegram host-control failure class is now explained by the
    bridge outage instead of an unexplained Telegram-layer miss

## Follow-Up

- Required follow-up: land the lifecycle/status hardening and update the open
  improvement candidate with the resulting control refs.
- Optional hardening: add a dedicated stage smoke or validator that checks the
  bridge-aware `status` surface after host restart so stage survivability is
  proven explicitly rather than inferred from a later Telegram request.
- Owner: `platform-engineering`
