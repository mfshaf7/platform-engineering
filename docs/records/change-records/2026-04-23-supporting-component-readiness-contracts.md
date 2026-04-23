# 2026-04-23 Supporting-component readiness contracts

## Summary

Standardized the shared `supporting component` tier with explicit verification
and support-readiness records instead of leaving shared stage and prod services
to look ready from Argo health, pod readiness, or operator-access reachability
alone.

This change adds:

- stage and prod verification records for the shared supporting components
- stage and prod support-readiness records for the same components
- component release-governance operator surfaces for the current shared
  contracts
- explicit inactive state for the intentionally suspended stage observability
  and stage dashboard surfaces

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `workspace-governance`
  - `security-architecture`
- workflow area:
  - release control
  - supporting component governance

## Ownership

- supporting-component release records and operator guidance:
  `platform-engineering`
- shared release-governance vocabulary and tier model:
  `workspace-governance`
- security review posture for shared secrets, database, and observability
  dependencies:
  `security-architecture`

## Root Cause

The shared release-control model already defined `supporting component` as a
first-class governance tier, but the platform still lacked concrete release
records for the components that stage and prod services actually depend on.

That left the platform vulnerable to false-ready state:

- shared secrets or database dependencies could be healthy in Kubernetes while
  lacking explicit release verification truth
- prod observability or dashboard assets could be reachable while having no
  governed support-readiness record for the exact contract
- intentionally suspended stage support surfaces could drift back into implied
  readiness instead of carrying explicit `inactive` status

## Source Changes

- `docs/components/README.md`
- `docs/components/vault/README.md`
- `docs/components/vault/release-governance.md`
- `docs/components/external-secrets/README.md`
- `docs/components/external-secrets/release-governance.md`
- `docs/components/platform-postgresql/README.md`
- `docs/components/platform-postgresql/release-governance.md`
- `docs/components/observability/README.md`
- `docs/components/observability/release-governance.md`
- `environments/shared/vault-release/`
- `environments/shared/external-secrets-release/`
- `environments/prod/platform-postgresql-release/`
- `environments/stage/observability-release/`
- `environments/prod/observability-release/`
- `environments/stage/platform-dashboards-release/`
- `environments/prod/platform-dashboards-release/`

## Artifact And Deployment Evidence

- shared secret source contract:
  - `environments/shared/argocd/vault-app.yaml`
- shared secret-delivery bridge contract:
  - `environments/shared/argocd/external-secrets-app.yaml`
- shared PostgreSQL contracts:
  - `environments/prod/argocd/platform-postgresql-app.yaml`
  - `environments/prod/argocd/platform-postgresql-secrets-app.yaml`
- observability contracts:
  - `environments/stage/argocd/observability-app.yaml`
  - `environments/prod/argocd/observability-app.yaml`
- dashboard asset contracts:
  - `environments/stage/argocd/platform-dashboards-app.yaml`
  - `environments/prod/argocd/platform-dashboards-app.yaml`

No live deployment artifact was changed in this tranche. The work standardizes
the release-governance records for the contracts already owned in Git.

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_governance_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_operational_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `git -C /home/mfshaf7/projects/platform-engineering diff --check`

## Follow-Up

- record real stage and prod verification evidence for the exact supporting
  component contracts before calling them governed-ready
- keep the stage observability and dashboard records `inactive` until those
  stage surfaces are deliberately resumed
- add the aggregate fail-closed environment readiness validator and operator
  workflow in the next tranche
