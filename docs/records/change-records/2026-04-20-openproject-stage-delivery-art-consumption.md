# 2026-04-20 openproject stage delivery art consumption

## Summary

Completed the governed stage handoff proof for the `accepted-idea-delivery`
workflow surface.

This rehearsal proves the documented handoff from the local
`accepted-idea-delivery` `dev-integration` profile into the governed live
runtime:

- accepted idea lookup through the live shared broker projection
- delivery-art project verification against the live platform-managed
  OpenProject runtime
- consume accepted idea through the broker-owned internal route
- durable backlink verification on the source proposal, delivery record, and
  broker projection

This does not create a separate OpenClaw-style OpenProject stage product. The
governed surface here is the live shared broker runtime plus the
platform-managed OpenProject runtime on the local cluster.

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

- governed stage/runtime evidence owner: `platform-engineering`
- broker source and API owner: `operator-orchestration-service`
- OpenProject proposal and delivery project model owner: `platform-engineering`
- bounded delivery-surface review owner: `security-architecture`

## Root Cause

The accepted-idea delivery workflow had already been proven in its admitted
local `dev-integration` lane and then confirmed on the rebuilt shared runtime,
but the explicit stage handoff contract still required one governed rehearsal
of the real live surface before the workflow could be treated as stage-ready.

Without that governed run, the workspace would still be relying on local-lane
proof and shared-runtime rollout evidence alone instead of the documented
`stage_handoff.required_checks` for the profile.

## Source Changes

- no new platform-owned source behavior in this record
- this record captures governed stage evidence after:
  - `2026-04-20 accepted idea delivery dev-integration admission`
  - `2026-04-20 operator-orchestration-service accepted-idea-delivery runtime rollout`
  - the bounded delivery-surface review in `security-architecture`

## Artifact And Deployment Evidence

- stage/shared platform revision:
  - `d277ecb7bacfc77f5984d961a46fcd6cbb8969ec`
- `platform-root-shared` Argo application revision:
  - `d277ecb7bacfc77f5984d961a46fcd6cbb8969ec`
- shared broker Argo application revision:
  - `d277ecb7bacfc77f5984d961a46fcd6cbb8969ec`
- shared broker source SHA:
  - `f575ba920c1f2a478f290e3d30ce67e0c6096fc2`
- shared broker image digest:
  - `sha256:938b2cd7e63709f7b75501cf13c1fd78a8d50e83d5b4c1858c84113da92aa93a`
- live OpenProject delivery ART project:
  - project id `37`
  - identifier `workspace-delivery-art`

## Live Verification

- shared broker runtime:
  - Argo child app `operator-orchestration-service` reached `Healthy Synced` on
    revision `d277ecb7bacfc77f5984d961a46fcd6cbb8969ec`
  - live broker pod:
    - `operator-orchestration-service-bc7c599b5-fh7lz`
  - broker self-checks from the live pod returned `200`:
    - `/healthz`:
      - `{"ok":true,"status":"live"}`
    - `/readyz`:
      - `{"ready":true,"failing":[],"checks":{"openproject":"reachable","openproject_target":"openproject://projects/workspace-proposals"}}`
    - `/version`:
      - `{"service":"operator-orchestration-service","version":"0.1.0","gitCommit":null,"callerAuthMode":"required"}`
- governed accepted-idea delivery rehearsal:
  - run id:
    - `aid-stage-20260420113444`
  - correlation ids:
    - capture: `aid-stage-20260420113444-capture`
    - triage: `aid-stage-20260420113444-triage`
    - decision: `aid-stage-20260420113444-decision`
    - lookup: `aid-stage-20260420113444-lookup`
    - consume: `aid-stage-20260420113444-consume`
    - final lookup: `aid-stage-20260420113444-final-lookup`
  - governed setup created and accepted source proposal:
    - `idea_id=idea-64`
    - `record_ref=openproject://work_packages/64`
  - accepted idea lookup returned:
    - `idea-64`
    - status `accepted`
  - delivery-art project verification returned:
    - project id `37`
    - identifier `workspace-delivery-art`
  - consume returned:
    - `delivery_created=true`
    - `source_updated=true`
    - `delivery_ref=openproject://work_packages/65`
    - `delivery_pm2_phase=Initiating`
    - `target_pi=PI-2026-02`
  - backlink verification confirmed:
    - broker projection `delivery_ref=openproject://work_packages/65`
    - source proposal `delivery_ref=openproject://work_packages/65`
    - delivery record `origin_idea_ref=idea-64`
    - delivery record `PM² Phase=Initiating`
    - delivery record `Target PI=PI-2026-02`

## Follow-Up

- the governed handoff is now proven for the current bounded internal consume
  surface
- do not treat this record as approval for:
  - a public ingress surface
  - Telegram delivery-management commands
  - automatic bidirectional synchronization
  - multi-ART routing
  - governed AI activation
- if the profile-owned stage handoff checks change later, update the profile
  contract, the profile README, and the next governed evidence record together
