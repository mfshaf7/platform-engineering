# Vault Release Governance

## Purpose

`vault` is a shared `supporting component`. It does not use a separate
candidate-and-readiness promotion lane, but stage and prod still require
current verification and support-readiness truth for the exact shared contract.

## Current Governance Shape

The shared Vault contract is recorded at:

- [../../../environments/shared/argocd/vault-app.yaml](../../../environments/shared/argocd/vault-app.yaml)

The supporting-component release records for that contract are:

- [../../../environments/shared/vault-release/stage-verification.yaml](../../../environments/shared/vault-release/stage-verification.yaml)
- [../../../environments/shared/vault-release/stage-support-readiness.yaml](../../../environments/shared/vault-release/stage-support-readiness.yaml)
- [../../../environments/shared/vault-release/prod-verification.yaml](../../../environments/shared/vault-release/prod-verification.yaml)
- [../../../environments/shared/vault-release/prod-support-readiness.yaml](../../../environments/shared/vault-release/prod-support-readiness.yaml)

Vault remains one shared runtime for both stage-facing and prod-facing secret
delivery. That shared runtime still needs separate stage and prod readiness
records because both lanes depend on it.

## Operator Flow

### 1. Update Or Confirm The Shared Contract

When Vault changes, update:

- [../../../environments/shared/argocd/vault-app.yaml](../../../environments/shared/argocd/vault-app.yaml)

### 2. Reset The Dependent Records When The Contract Changes

Refresh the affected verification and support-readiness files under:

- [../../../environments/shared/vault-release/](../../../environments/shared/vault-release/)

Keep the stage and prod records bound to the exact shared contract revision.

### 3. Rehearse The Shared Contract

Use the current Vault operator surfaces and runbooks to prove:

- Argo still matches the expected shared contract
- the shared Vault runtime is unsealed and healthy
- the API path still answers from the supported operator surface
- External Secrets can still rely on Vault as the shared upstream secret source

### 4. Record Verification

Write the exact rehearsal result into the stage or prod verification file for
the lane being assessed. Each record must carry:

- the exact shared contract reference
- an operator-reviewable `evidenceRef`
- explicit check results for the required verification pack

### 5. Record Support Readiness

Update the matching stage or prod support-readiness file only after the exact
verification record exists for the same contract revision.

## Evidence Rule

Unsealed status, UI reachability, and Argo health are required checks, not
sufficient proof by themselves.

Every Vault support-readiness record must remain tied to the exact shared
contract plus the exact verification record for the lane being assessed.

## Related Components

- [../external-secrets/README.md](../external-secrets/README.md)
- [operations.md](operations.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
