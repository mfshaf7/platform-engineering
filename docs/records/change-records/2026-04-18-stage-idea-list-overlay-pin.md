# 2026-04-18 stage idea-list overlay pin

## Summary

Pinned the stage Telegram overlay lane to the merged Telegram source that adds
broker-backed `/idea list` and `/idea show <idea-id>` plus clearer status-bearing
replies.

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

The previous stage overlay only covered broker-owned `/idea help` and single
record read proof. The next operator-visible gap is listing and clearer status
visibility directly from Telegram, which requires a new Telegram overlay build
from the merged source revision before stage can rehearse the expanded `/idea`
surface.

## Source Changes

- `environments/stage/release-candidate.yaml`
- `environments/stage/versions.yaml`
- `environments/stage/values/openclaw-gateway.yaml`
- `environments/stage/values/platform-version.yaml`
- `environments/stage/promotion-readiness.yaml`
- `environments/stage/verification.yaml`

## Artifact And Deployment Evidence

- pinned Telegram source SHA:
  - `8dca54ed1268bda7d97d0f8eee9930d57fe1f11e`
- pinned runtime-distribution SHA:
  - `ca8d8a00953ad6e71e97fd8c8183859ec22dac1a`
- overlay lane state after pin:
  - `pending-build`

## Live Verification

- `python3 products/openclaw/scripts/telegram_overlay_experiment.py pin stage --telegram-repo /home/mfshaf7/projects/openclaw-telegram-enhanced`
- `python3 products/openclaw/scripts/telegram_overlay_experiment.py validate stage`

## Follow-Up

- build the Telegram overlay image from the pinned source SHA
- record the resulting digest into the stage contract
- rehearse `/idea help`, `/idea list`, `/idea show <idea-id>`, and `/idea <text>` on stage
