# 2026-04-23 OpenProject governed release-governance state

## Summary

Standardized OpenProject as a governed `platform-integrated` product with
explicit release-state objects instead of treating the platform-managed product
contract as self-evidently ready from Argo health and localhost reachability.

This change adds:

- a governed stage candidate
- governed stage verification
- governed stage readiness
- governed prod post-promotion verification
- product-owned verification catalogs and operator guidance for those records

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `workspace-governance`
  - `operator-orchestration-service`
- workflow area:
  - release control
  - platform-integrated product governance

## Ownership

- OpenProject deployment contract, release-state objects, and operator guidance:
  `platform-engineering`
- delivery ART execution surface:
  `operator-orchestration-service`
- shared release-governance and evidence vocabulary:
  `workspace-governance`

## Root Cause

OpenProject already had a real platform-managed runtime, real operator access,
and a real ART data plane, but it did not yet expose governed release objects
for that product contract.

That left the platform vulnerable to a false-ready state:

- Argo health could be green while no current stage candidate or verification
  existed
- localhost reachability could work while there was no explicit readiness
  decision for the exact contract
- prod contract changes could land with no governed post-promotion verification
  state at all

## Source Changes

- `products/openproject/verification-catalog.yaml`
- `products/openproject/prod-verification-catalog.yaml`
- `products/openproject/runbooks/release-governance.md`
- `products/openproject/AGENTS.md`
- `products/openproject/README.md`
- `products/openproject/runtime-contract.md`
- `products/openproject/visibility-and-operations.md`
- `products/openproject/runbooks/README.md`
- `environments/prod/openproject-release/stage-candidate.yaml`
- `environments/prod/openproject-release/stage-verification.yaml`
- `environments/prod/openproject-release/stage-readiness.yaml`
- `environments/prod/openproject-release/prod-verification.yaml`

## Artifact And Deployment Evidence

- platform-owned OpenProject contract:
  - `environments/prod/argocd/openproject-app.yaml`
  - `environments/prod/argocd/openproject-secrets-app.yaml`
- supporting database contract:
  - `environments/prod/argocd/platform-postgresql-app.yaml`
- chart contract recorded:
  - `openproject/openproject@13.4.4`
- application image recorded:
  - `docker.io/openproject/openproject:17.2.3-slim`
- platform commit tied to the initial release records:
  - `a97d8715eb7b0b00d3a63ea66c59d40fde1af41a`

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_governance_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_operational_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `git -C /home/mfshaf7/projects/platform-engineering diff --check`
- live contract status captured while recording the tranche:
  - Argo apps:
    - `openproject` `Synced Healthy`
    - `openproject-secrets` `Synced Healthy`
  - External secrets:
    - `openproject-admin-secret` `SecretSynced`
    - `openproject-postgresql-credentials` `SecretSynced`

## Follow-Up

- record real stage verification and stage readiness approval for the exact
  current OpenProject candidate before calling it governed stage-ready
- record prod post-promotion verification whenever the OpenProject contract
  changes for governed prod use
- keep OpenProject described as `platform-integrated` until a distinct
  product-owned stage or promotion rail is deliberately created
