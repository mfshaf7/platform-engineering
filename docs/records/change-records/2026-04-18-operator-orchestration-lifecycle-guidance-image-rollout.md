# 2026-04-18 operator-orchestration-service lifecycle-guidance image rollout

## Summary

Pinned the shared `operator-orchestration-service` deployment to the rebuilt
broker image that adds canonical idea lifecycle guidance and the richer command
surface consumed by Telegram help and list rendering.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `operator-orchestration-service`
  - `openclaw-telegram-enhanced`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- shared runtime digest pin owner: `platform-engineering`
- broker source fix owner: `operator-orchestration-service`
- Telegram adapter source owner: `openclaw-telegram-enhanced`

## Root Cause

The live shared broker runtime still pointed at the earlier image built before
canonical lifecycle status guidance and `/idea list all` command semantics
landed on `main`. Until the new digest is pinned through `platform-engineering`,
stage cannot rehearse the final `/idea help` surface against the real broker
owner.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`

## Artifact And Deployment Evidence

- broker source SHA:
  - `1ed37bb16c8db9b2d6f447c24f038b5a70c7af39`
- rebuilt broker image:
  - `ghcr.io/mfshaf7/operator-orchestration-service`
- approved digest:
  - `sha256:40fac8f1ee3cdbb20ff0c1b81e13ffdf9bbef1ff10c00a4c98868497ec5399fe`
- build workflow run:
  - `operator-orchestration-service` Actions run `24604507911`

## Live Verification

- broker source build:
  - GitHub Actions log confirmed digest
- platform contract:
  - pending merge and shared Argo reconciliation

## Follow-Up

- merge the new broker image digest pin
- refresh `platform-root-shared`
- verify broker readiness before rehearsing the expanded Telegram overlay lane on stage
