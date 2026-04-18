# 2026-04-18 operator-orchestration-service idea-list image rollout

## Summary

Pinned the shared `operator-orchestration-service` deployment to the rebuilt
broker image that adds the broker-owned `idea-command` descriptor and bounded
idea list projection.

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
broker-owned idea listing and the broader `/idea` command-family descriptor
landed on `main`. Until the new digest is pinned through `platform-engineering`,
stage cannot rehearse `/idea list` and `/idea show <idea-id>` against the real
broker owner.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`

## Artifact And Deployment Evidence

- broker source SHA:
  - `05c567e5fed0808c8730347d6344bf1cd240739a`
- rebuilt broker image:
  - `ghcr.io/mfshaf7/operator-orchestration-service`
- approved digest:
  - `sha256:ea3752dc6f50545cbb8b525ce52725391aae5772a01011f8fa1de8f7363a366d`
- build workflow run:
  - `operator-orchestration-service` Actions run `24603782361`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh
  - broker rollout to the new digest
  - broker `/readyz` and `/version`
  - stage `/idea help`, `/idea list`, `/idea show <idea-id>`, and `/idea <text>`
    rehearsal against the corrected broker contract

## Follow-Up

- merge the new broker image digest pin
- refresh `platform-root-shared`
- verify broker readiness before rehearsing the expanded Telegram overlay lane on stage
