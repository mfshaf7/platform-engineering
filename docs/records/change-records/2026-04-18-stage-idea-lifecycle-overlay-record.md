# 2026-04-18 stage idea lifecycle overlay record

## Summary

Recorded the immutable stage Telegram overlay artifact built from the merged
Telegram source that adds lifecycle-aware `/idea help`, cleaner table-style
read surfaces, and `/idea list all`.

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

- stage overlay artifact contract owner: `platform-engineering`
- Telegram adapter source owner: `openclaw-telegram-enhanced`
- broker API owner: `operator-orchestration-service`

## Root Cause

The stage overlay pin only moved the contract to `pending-build`. Rehearsal
still required recording the exact immutable overlay artifact so Argo could
mount the correct Telegram runtime into the gateway pod.

## Source Changes

- `environments/stage/release-candidate.yaml`
- `environments/stage/versions.yaml`
- `environments/stage/values/openclaw-gateway.yaml`
- `environments/stage/values/platform-version.yaml`
- `environments/stage/promotion-readiness.yaml`
- `environments/stage/verification.yaml`

## Artifact And Deployment Evidence

- recorded stage candidate source bundle:
  - `8d1dabb18bf3`
- Telegram overlay source SHA:
  - `4a5c804ae59b0ffbd2b2c6ab3bd0e10be201b212`
- Telegram overlay image:
  - `ghcr.io/mfshaf7/openclaw-telegram-overlay@sha256:c31d68a1700e7b2f949ead8f63ae2979287eb1a2263e3ed959021d5897e310ff`
- Telegram overlay build workflow:
  - `platform-engineering` Actions run `24604621514`

## Live Verification

- `python3 products/openclaw/scripts/telegram_overlay_experiment.py record stage --digest sha256:c31d68a1700e7b2f949ead8f63ae2979287eb1a2263e3ed959021d5897e310ff --tag telegram-overlay-4a5c804ae59b`
- `python3 products/openclaw/scripts/telegram_overlay_experiment.py validate stage`

## Follow-Up

- merge the recorded overlay artifact into `main`
- reconcile stage and shared Argo apps
- verify `/idea help`, `/idea list`, `/idea list all`, `/idea show <idea-id>`,
  and `/idea <text>` on stage
