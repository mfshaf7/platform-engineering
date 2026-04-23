# External Secrets Release Governance

## Purpose

`external-secrets` is a shared `supporting component`. It bridges Vault into
Kubernetes secret delivery for both stage-facing and prod-facing workloads, so
its shared contract needs explicit verification and support-readiness records.

## Current Governance Shape

The shared External Secrets contract is recorded at:

- [../../../environments/shared/argocd/external-secrets-app.yaml](../../../environments/shared/argocd/external-secrets-app.yaml)

The supporting-component release records for that contract are:

- [../../../environments/shared/external-secrets-release/stage-verification.yaml](../../../environments/shared/external-secrets-release/stage-verification.yaml)
- [../../../environments/shared/external-secrets-release/stage-support-readiness.yaml](../../../environments/shared/external-secrets-release/stage-support-readiness.yaml)
- [../../../environments/shared/external-secrets-release/prod-verification.yaml](../../../environments/shared/external-secrets-release/prod-verification.yaml)
- [../../../environments/shared/external-secrets-release/prod-support-readiness.yaml](../../../environments/shared/external-secrets-release/prod-support-readiness.yaml)

## Operator Flow

### 1. Update Or Confirm The Shared Contract

When the shared External Secrets deployment changes, update:

- [../../../environments/shared/argocd/external-secrets-app.yaml](../../../environments/shared/argocd/external-secrets-app.yaml)

### 2. Reset The Dependent Records When The Contract Changes

Refresh the affected stage or prod verification and support-readiness files
under:

- [../../../environments/shared/external-secrets-release/](../../../environments/shared/external-secrets-release/)

### 3. Rehearse The Shared Contract

Use the current operator surfaces to prove:

- Argo still matches the expected shared chart contract
- controller pods are healthy
- one representative `ExternalSecret` still reconciles correctly
- Vault connectivity or auth still supports the shared secret-delivery path

### 4. Record Verification

Write the exact rehearsal result into the lane-specific verification file with:

- the exact shared contract reference
- an operator-reviewable `evidenceRef`
- explicit per-check results for the shared secret-delivery pack

### 5. Record Support Readiness

Update the matching stage or prod support-readiness file only after the exact
verification record exists for the same contract.

## Evidence Rule

Healthy controller pods or successful reconciliation of one secret alone do not
make the component ready by themselves. The record must tie the shared contract
to reviewable evidence and the exact verification result.

## Related Components

- [../vault/README.md](../vault/README.md)
- [operations.md](operations.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
