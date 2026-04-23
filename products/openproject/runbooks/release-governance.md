# OpenProject Release Governance

## Purpose

This runbook defines the governed release-state model for OpenProject on the
shared platform.

OpenProject remains a `platform-integrated` product. These records govern the
platform-owned deployment contract for the product; they do not create a
separate OpenProject-owned `source -> stage -> prod` artifact lane.

## Current Governance Shape

The current OpenProject runtime is one platform-managed contract under
`environments/prod/argocd/`.

The governed release records for that contract live in:

- [../../../environments/prod/openproject-release/stage-candidate.yaml](../../../environments/prod/openproject-release/stage-candidate.yaml)
- [../../../environments/prod/openproject-release/stage-verification.yaml](../../../environments/prod/openproject-release/stage-verification.yaml)
- [../../../environments/prod/openproject-release/stage-readiness.yaml](../../../environments/prod/openproject-release/stage-readiness.yaml)
- [../../../environments/prod/openproject-release/prod-verification.yaml](../../../environments/prod/openproject-release/prod-verification.yaml)

These stage objects are platform-owned approval records for the current
OpenProject deployment contract. They do not imply a separate long-lived stage
namespace or a product-owned promotion rail already exists.

## Current Deployment Contract

The current product contract is owned in:

- [../../../environments/prod/argocd/openproject-app.yaml](../../../environments/prod/argocd/openproject-app.yaml)
- [../../../environments/prod/argocd/openproject-secrets-app.yaml](../../../environments/prod/argocd/openproject-secrets-app.yaml)

OpenProject also depends on the shared PostgreSQL contract at:

- [../../../environments/prod/argocd/platform-postgresql-app.yaml](../../../environments/prod/argocd/platform-postgresql-app.yaml)

## Product-Owned Verification Catalogs

The current OpenProject verification packs are:

- [../verification-catalog.yaml](../verification-catalog.yaml)
- [../prod-verification-catalog.yaml](../prod-verification-catalog.yaml)

Use these catalogs when recording release evidence. Do not invent
OpenProject-local check IDs in the release objects unless the product contract
actually changed and the catalogs were updated first.

## Operator Flow

### 1. Update Or Confirm The Platform-Owned Contract

When OpenProject changes through the governed platform path, update the
platform-owned contract first:

- [../../../environments/prod/argocd/openproject-app.yaml](../../../environments/prod/argocd/openproject-app.yaml)
- [../../../environments/prod/argocd/openproject-secrets-app.yaml](../../../environments/prod/argocd/openproject-secrets-app.yaml)

If the external database dependency changed for the product contract, update:

- [../../../environments/prod/argocd/platform-postgresql-app.yaml](../../../environments/prod/argocd/platform-postgresql-app.yaml)

### 2. Record Or Refresh The Stage Candidate

Update:

- [../../../environments/prod/openproject-release/stage-candidate.yaml](../../../environments/prod/openproject-release/stage-candidate.yaml)

This records the exact contract OpenProject would rely on for the next governed
rehearsal or approval pass.

When that candidate changes, reset:

- [../../../environments/prod/openproject-release/stage-verification.yaml](../../../environments/prod/openproject-release/stage-verification.yaml)
- [../../../environments/prod/openproject-release/stage-readiness.yaml](../../../environments/prod/openproject-release/stage-readiness.yaml)
- [../../../environments/prod/openproject-release/prod-verification.yaml](../../../environments/prod/openproject-release/prod-verification.yaml)

### 3. Rehearse The Current Candidate

Use the existing OpenProject operator surfaces for the exact contract:

- `make openproject-status`
- `make openproject-access`
- `make openproject-check-delivery-art-quality`

At minimum, collect evidence for:

- supported operator access path reaches `/login`
- Vault-backed admin secret is synchronized or the supported sync path succeeds
- PostgreSQL dependency is reachable for the runtime
- web and worker workloads stay stable after reconciliation
- ART quality still passes for the current delivery plane

### 4. Record Stage Verification

Write the rehearsal result into:

- [../../../environments/prod/openproject-release/stage-verification.yaml](../../../environments/prod/openproject-release/stage-verification.yaml)

The record must point at:

- the exact stage-candidate file
- an operator-reviewable `evidenceRef`
- explicit per-check results from [../verification-catalog.yaml](../verification-catalog.yaml)

### 5. Approve Or Reject Stage Readiness

Update:

- [../../../environments/prod/openproject-release/stage-readiness.yaml](../../../environments/prod/openproject-release/stage-readiness.yaml)

Readiness must remain `pending` unless the exact current candidate has matching
verification evidence.

### 6. Record Prod Post-Promotion Verification

Whenever the OpenProject prod contract changes for governed use, update:

- [../../../environments/prod/openproject-release/prod-verification.yaml](../../../environments/prod/openproject-release/prod-verification.yaml)

That record must point back to the current prod contract and capture the
post-promotion checks from [../prod-verification-catalog.yaml](../prod-verification-catalog.yaml).

## Evidence Rule

Argo health, secret sync, and HTTP reachability are required checks, not
sufficient proof.

Every OpenProject verification record must carry:

- exact candidate or prod-contract reference
- operator-reviewable `evidenceRef`
- explicit check results for the current product-owned catalog

## Current Constraint

OpenProject still does not have a separate product-governed stage runtime.

That means:

- the release objects are real and required
- stage verification and readiness can fail closed against the platform-owned
  contract
- the product still must not be described as having a separate OpenProject
  `source -> stage -> prod` rollout train
