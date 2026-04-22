# 2026-04-22 operator-orchestration-service shared release governance state

## Summary

Standardized `operator-orchestration-service` as a governed shared
control-plane component with explicit stage and prod release-state records
instead of treating the shared deployment digest as self-evidently ready.

The shared deployment contract remains the live runtime truth, but stage
candidate, stage verification, stage readiness, and prod verification now
exist as first-class release objects that point back to that exact contract.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `operator-orchestration-service`
  - `security-architecture`
- trust-boundary areas:
  - delivery
  - runtime

## Ownership

- shared deployment contract and release-state objects:
  `platform-engineering`
- component-owned verification catalogs and source metadata artifact:
  `operator-orchestration-service`
- release-governance trust-boundary review:
  `security-architecture`

## Root Cause

The broker already built images and ran as a live shared control-plane
component, but it had no governed release state beyond the deployment digest
pin in `environments/shared/operator-orchestration-service/deployment.yaml`.

That left stage and prod vulnerable to a false-ready state:

- Argo health could be green while the current broker contract had no recorded
  candidate
- no verification record identified which checks were actually exercised
- no readiness decision or prod post-promotion verification captured whether
  the shared control-plane behavior was still safe to rely on

## Source Changes

- `environments/shared/operator-orchestration-service/stage-candidate.yaml`
- `environments/shared/operator-orchestration-service/stage-verification.yaml`
- `environments/shared/operator-orchestration-service/stage-readiness.yaml`
- `environments/shared/operator-orchestration-service/prod-verification.yaml`
- `docs/components/operator-orchestration-service/release-governance.md`
- `docs/components/operator-orchestration-service/README.md`
- `docs/components/operator-orchestration-service/architecture.md`
- `docs/components/operator-orchestration-service/operations.md`

## Artifact And Deployment Evidence

- shared deployment contract:
  - `environments/shared/operator-orchestration-service/deployment.yaml`
- recorded shared broker digest:
  - `ghcr.io/mfshaf7/operator-orchestration-service@sha256:938b2cd7e63709f7b75501cf13c1fd78a8d50e83d5b4c1858c84113da92aa93a`
- broker source SHA recorded from the existing rollout evidence:
  - `f575ba920c1f2a478f290e3d30ce67e0c6096fc2`
- platform deployment revision tied to that rollout:
  - `9b87557ea2f2f1ff80586d0e614bc921ab585d7e`

## Live Verification

- `python3 scripts/validate_governance_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_operational_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `git -C /home/mfshaf7/projects/platform-engineering diff --check`

## Follow-Up

- record real stage verification and stage readiness approval for the exact
  shared broker candidate before calling the component stage-ready
- record prod post-promotion verification whenever the shared broker contract
  changes for prod-facing use
- extend aggregate environment readiness so this shared control-plane state
  becomes a hard gate instead of documentation alone
