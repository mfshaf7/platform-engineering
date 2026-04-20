# 2026-04-20 operator-orchestration-service accepted-idea-delivery runtime rollout

## Summary

Pinned the shared `operator-orchestration-service` deployment to the rebuilt
broker image that carries the internal accepted-idea delivery consume path,
the socket-reset hardening for the long-running broker transport, the
write-success/read-failure backlink recovery for the source proposal PATCH, the
retry hardening for the delivery-project preflight lookup, the generalized
safe-read retry policy across broker OpenProject projections, and the live
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
  - `f575ba920c1f2a478f290e3d30ce67e0c6096fc2`
- published broker image:
  - `ghcr.io/mfshaf7/operator-orchestration-service`
- published digest resolved from tag `sha-f575ba9`:
  - `sha256:938b2cd7e63709f7b75501cf13c1fd78a8d50e83d5b4c1858c84113da92aa93a`
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

- shared runtime deployment:
  - Argo child app `operator-orchestration-service` reached `Healthy Synced` on
    revision `9b87557ea2f2f1ff80586d0e614bc921ab585d7e`
  - deployment spec image:
    - `ghcr.io/mfshaf7/operator-orchestration-service@sha256:938b2cd7e63709f7b75501cf13c1fd78a8d50e83d5b4c1858c84113da92aa93a`
  - live broker pod:
    - `operator-orchestration-service-bc7c599b5-fh7lz`
  - broker self-checks from the live pod returned `200`:
    - `/healthz`:
      - `{"ok":true,"status":"live"}`
    - `/readyz`:
      - `{"ready":true,"failing":[],"checks":{"openproject":"reachable","openproject_target":"openproject://projects/workspace-proposals"}}`
    - `/version`:
      - `{"service":"operator-orchestration-service","version":"0.1.0","gitCommit":null,"callerAuthMode":"required"}`
- governed shared-runtime consume confirmation:
  - run id:
    - `aid-live-20260420112208`
  - correlation ids:
    - capture: `aid-live-20260420112208-capture`
    - triage: `aid-live-20260420112208-triage`
    - decision: `aid-live-20260420112208-decision`
    - lookup: `aid-live-20260420112208-lookup`
    - consume: `aid-live-20260420112208-consume`
    - final lookup: `aid-live-20260420112208-final-lookup`
  - accepted idea lookup returned:
    - `idea-62`
  - delivery-art project verification returned:
    - project id `37`
    - identifier `workspace-delivery-art`
  - consume returned:
    - `delivery_created=true`
    - `source_updated=true`
    - `delivery_ref=openproject://work_packages/63`
    - `delivery_pm2_phase=Initiating`
    - `target_pi=PI-2026-02`
  - backlink verification confirmed:
    - broker projection `delivery_ref=openproject://work_packages/63`
    - source proposal `delivery_ref=openproject://work_packages/63`
    - delivery record `origin_idea_ref=idea-62`
    - delivery record `PM² Phase=Initiating`
    - delivery record `Target PI=PI-2026-02`

## Follow-Up Actions

- the shared-runtime rollout is complete; do not use this record as a
  substitute for governed `stage` evidence
- stage handoff still requires a separate stage rehearsal and stage evidence
  record for accepted-idea delivery
