# 2026-04-19 stage idea lifecycle overlay record

## Summary

Recorded the immutable stage Telegram overlay artifact built from the merged
Telegram source that adds the bounded `/idea` lifecycle command surface:

- `/idea triage <idea-id> <summary>`
- `/idea decide <idea-id> <parked|accepted|rejected> <notes>`
- `/idea show <idea-id>` readback of triage, decision, and evaluation metadata

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `openclaw-telegram-enhanced`
  - `operator-orchestration-service`
- trust-boundary areas:
  - delivery
  - runtime
  - AI

## Ownership

- stage overlay artifact contract owner: `platform-engineering`
- Telegram adapter source owner: `openclaw-telegram-enhanced`
- broker API owner: `operator-orchestration-service`

## Root Cause

The stage overlay lane still pointed at the earlier Telegram source and did not
carry the landed triage, bounded decision, and richer `/idea show` rendering.
Stage rehearsal required recording the new immutable overlay artifact against
the already-qualified OpenClaw base image before Argo could mount the updated
Telegram runtime.

## Source Changes

- `environments/stage/release-candidate.yaml`
- `environments/stage/versions.yaml`
- `environments/stage/values/openclaw-gateway.yaml`
- `environments/stage/values/platform-version.yaml`
- `environments/stage/promotion-readiness.yaml`
- `environments/stage/verification.yaml`

## Artifact And Deployment Evidence

- recorded stage candidate source bundle:
  - `f51f50083f7c`
- Telegram overlay source SHA:
  - `695e222a44cb60bd10af9662c3c2fe38b981cefc`
- Telegram overlay image:
  - `ghcr.io/mfshaf7/openclaw-telegram-overlay@sha256:5364a660d9f30ce28db0b640cdea59d3fef987a7fc8ab197f169d5f7b7a09ba8`
- Telegram overlay build workflow:
  - `platform-engineering` Actions run `24618628701`

## Live Verification

- `python3 products/openclaw/scripts/telegram_overlay_experiment.py record stage --digest sha256:5364a660d9f30ce28db0b640cdea59d3fef987a7fc8ab197f169d5f7b7a09ba8 --tag telegram-overlay-695e222a44cb --platform-sha bb1c3d876ae6aa570cdf6f86109252964dd76c91`
- `python3 products/openclaw/scripts/telegram_overlay_experiment.py validate stage`

## Follow-Up

- merge the recorded overlay artifact into `main`
- reconcile stage and shared Argo apps
- verify `/idea help`, `/idea triage`, `/idea decide`, `/idea show`, and the
  underlying broker lifecycle surface on stage
