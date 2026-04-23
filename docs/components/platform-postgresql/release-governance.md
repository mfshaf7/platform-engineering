# Platform PostgreSQL Release Governance

## Purpose

`platform-postgresql` is a shared `supporting component`. It does not have a
standalone product promotion lane, but the shared database contract still
needs explicit verification and support-readiness state for both stage-facing
and prod-facing governed services.

## Current Governance Shape

The current platform-managed PostgreSQL contract is recorded at:

- [../../../environments/prod/argocd/platform-postgresql-app.yaml](../../../environments/prod/argocd/platform-postgresql-app.yaml)
- [../../../environments/prod/argocd/platform-postgresql-secrets-app.yaml](../../../environments/prod/argocd/platform-postgresql-secrets-app.yaml)

The supporting-component release records for that contract are:

- [../../../environments/prod/platform-postgresql-release/stage-verification.yaml](../../../environments/prod/platform-postgresql-release/stage-verification.yaml)
- [../../../environments/prod/platform-postgresql-release/stage-support-readiness.yaml](../../../environments/prod/platform-postgresql-release/stage-support-readiness.yaml)
- [../../../environments/prod/platform-postgresql-release/prod-verification.yaml](../../../environments/prod/platform-postgresql-release/prod-verification.yaml)
- [../../../environments/prod/platform-postgresql-release/prod-support-readiness.yaml](../../../environments/prod/platform-postgresql-release/prod-support-readiness.yaml)

Stage-facing OpenProject rehearsal currently depends on this same prod-managed
database contract. These records do not imply a separate long-lived stage
database exists today.

## Operator Flow

### 1. Update Or Confirm The Shared Contract

When the shared database or its secret-delivery contract changes, update:

- [../../../environments/prod/argocd/platform-postgresql-app.yaml](../../../environments/prod/argocd/platform-postgresql-app.yaml)
- [../../../environments/prod/argocd/platform-postgresql-secrets-app.yaml](../../../environments/prod/argocd/platform-postgresql-secrets-app.yaml)

### 2. Reset The Dependent Records When The Contract Changes

Refresh the affected stage or prod verification and support-readiness files
under:

- [../../../environments/prod/platform-postgresql-release/](../../../environments/prod/platform-postgresql-release/)

### 3. Rehearse The Current Contract

Use the existing PostgreSQL and OpenProject operator surfaces to prove:

- Argo still matches the expected database and secret contract
- the database runtime is healthy
- credential delivery still matches the contract
- the current OpenProject consumer can still connect through the shared
  service

### 4. Record Verification

Write the exact rehearsal result into the stage or prod verification file with:

- the exact shared contract reference
- an operator-reviewable `evidenceRef`
- explicit per-check results for the current supporting-component pack

### 5. Record Support Readiness

Update the matching stage or prod support-readiness file only after the exact
verification record exists for the same contract revision.

## Evidence Rule

Pod readiness or one successful connection alone does not make the database
support-ready. The record must tie the exact database contract, secret
contract, and operator-reviewable proof together.

## Related Components

- [operations.md](operations.md)
- [../../../products/openproject/runbooks/release-governance.md](../../../products/openproject/runbooks/release-governance.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
