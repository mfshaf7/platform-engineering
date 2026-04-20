# 2026-04-20 operator-orchestration-service accepted-idea-delivery runtime rollout

## Summary

Pinned the shared `operator-orchestration-service` deployment to the rebuilt
broker image that carries the internal accepted-idea delivery consume path,
the socket-reset hardening for the long-running broker transport, and the live
OpenProject delivery-project env contract in the shared runtime.

This rollout also required one live OpenProject convergence step before the
runtime could become ready for rehearsal:

- seed the canonical `workspace-delivery-art` project model
- grant the broker automation identity access to both `workspace-proposals`
  and `workspace-delivery-art`
- reconverge the proposal backlog model so the live `Delivery Ref` custom field
  exists for durable source backlinks

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `platform-engineering`
  - `operator-orchestration-service`
  - `security-architecture`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- shared runtime digest pin owner: `platform-engineering`
- broker source owner: `operator-orchestration-service`
- bounded expansion review owner: `security-architecture`

## Root Cause

The accepted-idea delivery source work landed on `main`, but the governed shared
broker runtime still pointed at the older lifecycle-only image and only carried
proposal-plane OpenProject env values.

Until the shared deployment pin moved to the rebuilt image and the delivery
project ids and backlink custom-field ids were wired, the real runtime had no
supported way to exercise `POST /v1/ideas/{idea_id}/consume` against the live
OpenProject delivery ART.

The live OpenProject backlog model was also one contract revision behind:
`Delivery Ref` was missing from `workspace-proposals`, so even a correct broker
runtime would not have been able to persist the source backlink durably.

## Source Changes

- `environments/shared/operator-orchestration-service/deployment.yaml`

## Artifact And Deployment Evidence

- broker source SHA:
  - `08bea2c7f835be33fa8d46ce29de564074db445f`
- published broker image:
  - `ghcr.io/mfshaf7/operator-orchestration-service`
- published digest resolved from tag `sha-08bea2c`:
  - `sha256:2047270e491209797462e7470fd22a8c2cce92bc9367101e4c539367e1a79fb2`
- live OpenProject delivery ART project:
  - project id `37`
  - identifier `workspace-delivery-art`
- live delivery env ids:
  - top-level type `Epic`: `38`
  - delivery status `new`: `67`
  - source backlog custom field `Delivery Ref`: `25`
  - delivery custom field `Origin Idea Ref`: `12`
  - delivery custom field `PM² Phase`: `11`
  - delivery custom field `Target PI`: `16`

## Live Verification

- pending after merge:
  - `platform-root-shared` refresh onto the new deployment manifest
  - broker pod rollout to digest `sha256:2047270e491209797462e7470fd22a8c2cce92bc9367101e4c539367e1a79fb2`
  - broker `/healthz`, `/readyz`, and `/version`
  - one governed consume rehearsal against the real OpenProject runtime with:
    - accepted idea lookup
    - delivery-art project verification
    - consume accepted idea
    - backlink verification

## Follow-Up Actions

- merge this shared runtime rollout first
- wait for Argo to reconcile `operator-orchestration-service`
- capture the governed live rehearsal in a separate stage evidence record
