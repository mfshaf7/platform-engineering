# 2026-04-18 operator-orchestration-service host-header image rollout

## Summary

Pinned the shared `operator-orchestration-service` deployment to the rebuilt
broker image that honors the reviewed OpenProject host-header runtime contract.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `operator-orchestration-service`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- shared runtime digest pin owner: `platform-engineering`
- broker source fix owner: `operator-orchestration-service`

## Root Cause

The prior shared runtime digest pointed at the broker image built before the
OpenProject host-header runtime fix. Even after the platform deployment
contract was corrected, the live runtime could not become ready until the
rebuilt broker image was approved and pinned.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`

## Artifact And Deployment Evidence

- broker source SHA:
  - `74c6ec8ee8570d8ca9af18078796a0bb18f022e0`
- rebuilt broker image:
  - `ghcr.io/mfshaf7/operator-orchestration-service`
- approved digest:
  - `sha256:0b93a00811f0286339f6873297cacbc4bb6f91e046852bf99df8c4bf42d40723`
- build workflow run:
  - `operator-orchestration-service` Actions run `24601794354`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh
  - broker rollout to the new digest
  - broker `/readyz` and `/version`
  - stage `/idea` capture rehearsal

## Follow-Up

- merge the new broker image digest pin
- refresh `platform-root-shared`
- verify broker readiness and continue the stage capture lane
