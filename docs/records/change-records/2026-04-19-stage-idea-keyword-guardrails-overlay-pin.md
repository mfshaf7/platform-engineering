# 2026-04-19 stage idea keyword guardrails overlay pin

## Summary

Pinned the stage Telegram overlay lane to the merged Telegram source that
prevents malformed `/idea` command keywords from falling through into raw idea
capture.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `openclaw-telegram-enhanced`
  - `operator-orchestration-service`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- stage overlay contract owner: `platform-engineering`
- Telegram command adapter owner: `openclaw-telegram-enhanced`
- broker API owner: `operator-orchestration-service`

## Root Cause

The previous stage overlay still pointed at Telegram source
`695e222a44cb60bd10af9662c3c2fe38b981cefc`, so stage kept the older parser
behavior that could treat malformed `/idea decide ...` attempts as new idea
captures. The source fix was merged in `openclaw-telegram-enhanced`, but stage
was not yet repinned to that newer source.

## Source Changes

- `environments/stage/release-candidate.yaml`
- `environments/stage/versions.yaml`
- `environments/stage/values/openclaw-gateway.yaml`
- `environments/stage/values/platform-version.yaml`
- `environments/stage/promotion-readiness.yaml`
- `environments/stage/verification.yaml`

## Artifact And Deployment Evidence

- pinned Telegram source SHA:
  - `d7390578c440f10a47dcc47881dc72a96af9aa0b`
- pinned runtime-distribution SHA:
  - `9c2ae383adcb8d11a694124948c5898e653076b4`
- overlay lane state after pin:
  - `pending-build`
- expected overlay tag:
  - `telegram-overlay-d7390578c440`

## Live Verification

- `python3 products/openclaw/scripts/telegram_overlay_experiment.py pin stage --telegram-repo /home/mfshaf7/projects/openclaw-telegram-enhanced`
- `python3 products/openclaw/scripts/telegram_overlay_experiment.py validate stage`

## Follow-Up

- build the Telegram overlay image from the pinned source SHA
- record the resulting digest into the stage contract
- reconcile and rehearse `/idea triage` and `/idea decide` error handling on
  stage
