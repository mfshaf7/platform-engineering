# Change Record

## Summary

- Date: 2026-04-03
- Short title: Telegram runtime contract and helper import fix
- Environment: prod
- Severity: high

## Classification

- Type: app/plugin source bug
- User-facing impact: Telegram topics could not start or process messages correctly in prod.

## Ownership

- Owning repo or layer: `openclaw-telegram-enhanced`
- Related repos: `platform-engineering`

## Root Cause

- Immediate failure: Telegram provider either failed at startup or failed during message handling.
- Actual root cause: the prod Telegram bundle carried incompatible runtime contracts, including an incorrect helper import for `appendHostControlTopicSystemPrompt`.
- Why it escaped earlier controls: there was no bundle validator for the helper import mismatch and prod had an older pinned Telegram contract.

## Source Changes

- Repo: `openclaw-telegram-enhanced`
- Commit(s): `7c92750ec69d380ebfae1aa5beb23a69d01debcd`
- Guardrail added:
  - validator in `platform-engineering/scripts/validate_gateway_source_bundle.py`

## Artifact And Deployment Evidence

- Build workflow run: GitHub Actions `Build Gateway Image`
- Published image tag: `prod-3c16f4f10a92`
- Published digest: `sha256:c3691ae4747237768d0129be3ae280621a94d9091f5e3892d116b73c1865ee9e`
- Recorded prod revision: `695a66611c5028d002951719bf1c8fe025ebd52f`
- Argo application revision: `695a66611c5028d002951719bf1c8fe025ebd52f`

## Host Or Runtime Recovery

- Required host/runtime action: None for the source fix itself.
- Why it was environment drift instead of source defect: Not applicable.
- Recovery command or procedure: None.

## Live Verification

- App health: Argo `Synced Healthy`
- Deployed image: `<governed-gateway-image>@sha256:c3691ae4747237768d0129be3ae280621a94d9091f5e3892d116b73c1865ee9e`
- Pod: `openclaw-gateway-66cbc7447d-m2mss`
- Functional verification: prod bot provider started cleanly and outbound verification DM succeeded
- Residual risk: non-host-control topics still depended on host Ollama reachability

## Follow-Up

- Required follow-up: fix deployment-owned workspace drift for `security-architecture`
- Optional hardening: add more Telegram contract validators
- Owner: platform engineering
