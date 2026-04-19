# 2026-04-19 operator-orchestration-service idea-lifecycle image rollout

## Summary

Pinned the shared `operator-orchestration-service` deployment to the rebuilt
broker image that carries the landed `/idea` lifecycle surface:

- operator-authored triage
- bounded decision for `parked`, `accepted`, and `rejected`
- internal evaluation metadata writes with readback through `/idea show`

The shared deployment contract now also wires the OpenProject status ids,
evaluation custom-field ids, and workspace vocabulary tokens required by that
surface.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `operator-orchestration-service`
  - `openclaw-telegram-enhanced`
- trust-boundary areas:
  - delivery
  - runtime
  - AI

## Ownership

- shared runtime digest pin owner: `platform-engineering`
- broker source owner: `operator-orchestration-service`
- Telegram adapter source owner: `openclaw-telegram-enhanced`

## Root Cause

The shared broker deployment still pointed at the older image and older runtime
env surface that predated triage, bounded decision, and internal evaluation
metadata. Until the shared deployment pin moves to the rebuilt broker image and
the new env values are wired, stage cannot rehearse the actual landed `/idea`
lifecycle slice.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`

## Artifact And Deployment Evidence

- broker source SHA:
  - `a46fcb57aedfd55f9bb93fee6aea39c9f19b6972`
- rebuilt broker image:
  - `ghcr.io/mfshaf7/operator-orchestration-service`
- approved digest:
  - `sha256:b948c5b26c847428ca8e5b2556a1adb30b40adb09770c14ce4279c198dbfc5da`
- build workflow run:
  - `operator-orchestration-service` Actions run `24618136082`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh
  - shared broker rollout to the new digest
  - broker `/readyz` and `/version`
  - stage `/idea triage`, `/idea decide`, `/idea show`, and evaluation readback
    rehearsal against the corrected shared broker contract

## Follow-Up

- merge the new broker image digest pin and env contract
- refresh `platform-root-shared`
- verify broker readiness before rehearsing the expanded Telegram overlay lane
  on stage
