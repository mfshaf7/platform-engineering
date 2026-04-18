# 2026-04-18 stage idea lifecycle overlay pin

## Summary

Pinned the stage Telegram overlay lane to the merged Telegram source that adds
broker-owned lifecycle guidance, cleaner table-style `/idea` rendering, and
`/idea list all`.

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

The previous stage overlay captured broker-owned help and basic read/list
behavior, but it still predated the richer lifecycle guidance, table-style
presentation, and explicit `/idea list all` operator flow.

## Source Changes

- `environments/stage/release-candidate.yaml`
- `environments/stage/versions.yaml`
- `environments/stage/values/openclaw-gateway.yaml`
- `environments/stage/values/platform-version.yaml`
- `environments/stage/promotion-readiness.yaml`
- `environments/stage/verification.yaml`

## Artifact And Deployment Evidence

- pinned Telegram source SHA:
  - `4a5c804ae59b0ffbd2b2c6ab3bd0e10be201b212`
- pinned runtime-distribution SHA:
  - `ca8d8a00953ad6e71e97fd8c8183859ec22dac1a`
- overlay lane state after pin:
  - `pending-build`
- expected overlay tag:
  - `telegram-overlay-4a5c804ae59b`

## Live Verification

- `python3 products/openclaw/scripts/telegram_overlay_experiment.py pin stage --telegram-repo /home/mfshaf7/projects/openclaw-telegram-enhanced`
- `python3 products/openclaw/scripts/telegram_overlay_experiment.py validate stage`

## Follow-Up

- build the Telegram overlay image from the pinned source SHA
- record the resulting digest into the stage contract
- rehearse `/idea help`, `/idea list`, `/idea list all`, `/idea show <idea-id>`,
  and `/idea <text>` on stage
