# 2026-04-18 operator-orchestration-service workflow-catalog image rollout

## Summary

Pinned the shared `operator-orchestration-service` deployment to the rebuilt
broker image that owns canonical workflow descriptors and bounded idea read
projection for the `/idea` lane.

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
- Telegram adapter source fix owner: `openclaw-telegram-enhanced`

## Root Cause

The live shared broker runtime still pointed at the earlier image built before
the broker-owned workflow catalog and read projection landed on `main`. Until
that digest is pinned through `platform-engineering`, stage cannot rehearse the
correct `/idea help` contract against the real broker owner.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`

## Artifact And Deployment Evidence

- broker source SHA:
  - `e09a8e0506df8ade8b3bd67ec14f57f288683562`
- rebuilt broker image:
  - `ghcr.io/mfshaf7/operator-orchestration-service`
- approved digest:
  - `sha256:671aeef58be1cd13fb5b90e85a6def35798d302ca5be228a6ff070aa645e0b2d`
- build workflow run:
  - `operator-orchestration-service` Actions run `24603014188`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh
  - broker rollout to the new digest
  - broker `/readyz` and `/version`
  - stage `/idea help` and `/idea` rehearsal against the corrected broker-owned contract

## Follow-Up

- merge the new broker image digest pin
- refresh `platform-root-shared`
- verify broker readiness before rolling the new Telegram overlay on stage
