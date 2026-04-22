# Operator Orchestration Service Release Governance

## Purpose

`operator-orchestration-service` is a shared control-plane component. It uses
one shared deployment today, but that does not remove the need for governed
stage and prod release truth.

This component now follows the shared-control-plane tier from
[../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md):

- stage candidate
- stage verification
- stage readiness decision
- prod environment contract
- prod post-promotion verification

## Current Runtime Truth

The current live shared broker contract is still the shared deployment at:

- [../../../environments/shared/operator-orchestration-service/deployment.yaml](../../../environments/shared/operator-orchestration-service/deployment.yaml)

That file is the authoritative deployed environment contract for this component
today.

The current stage and prod release-state objects are:

- [../../../environments/shared/operator-orchestration-service/stage-candidate.yaml](../../../environments/shared/operator-orchestration-service/stage-candidate.yaml)
- [../../../environments/shared/operator-orchestration-service/stage-verification.yaml](../../../environments/shared/operator-orchestration-service/stage-verification.yaml)
- [../../../environments/shared/operator-orchestration-service/stage-readiness.yaml](../../../environments/shared/operator-orchestration-service/stage-readiness.yaml)
- [../../../environments/shared/operator-orchestration-service/prod-verification.yaml](../../../environments/shared/operator-orchestration-service/prod-verification.yaml)

## Component-Owned Verification Catalogs

The component-specific checks are owned in the source repo:

- [`operator-orchestration-service/verification-catalog.yaml`](https://github.com/mfshaf7/operator-orchestration-service/blob/main/verification-catalog.yaml)
- [`operator-orchestration-service/prod-verification-catalog.yaml`](https://github.com/mfshaf7/operator-orchestration-service/blob/main/prod-verification-catalog.yaml)

The platform repo should record release truth against those catalogs, not
invent workload-local checks independently.

## Operator Flow

### 1. Build Or Identify The Candidate Artifact

Use the source-owned image build in `operator-orchestration-service` and keep
the workflow run metadata for the exact digest.

At minimum capture:

- image repository
- digest
- source SHA
- workflow run id or artifact reference

### 2. Record Or Update The Shared Deployment Contract

If the candidate changes the live shared contract, update:

- [../../../environments/shared/operator-orchestration-service/deployment.yaml](../../../environments/shared/operator-orchestration-service/deployment.yaml)

The shared deployment contract is the prod environment contract for this
component today. There is no separate stage-only broker deployment yet.

### 3. Record The Stage Candidate

Update:

- [../../../environments/shared/operator-orchestration-service/stage-candidate.yaml](../../../environments/shared/operator-orchestration-service/stage-candidate.yaml)

When the candidate changes, reset both:

- [../../../environments/shared/operator-orchestration-service/stage-verification.yaml](../../../environments/shared/operator-orchestration-service/stage-verification.yaml)
- [../../../environments/shared/operator-orchestration-service/stage-readiness.yaml](../../../environments/shared/operator-orchestration-service/stage-readiness.yaml)

This keeps rehearsal and approval bound to the exact candidate.

### 4. Rehearse The Candidate

Run the shared broker checks from:

- [operations.md](operations.md)

Then exercise the stage verification catalog against the current candidate:

- runtime start and readiness
- workflow catalog visibility
- OpenProject adapter readiness
- one representative bounded workflow path

### 5. Record Stage Verification

Write the exact evidence into:

- [../../../environments/shared/operator-orchestration-service/stage-verification.yaml](../../../environments/shared/operator-orchestration-service/stage-verification.yaml)

The record must point at:

- the exact stage candidate file
- an operator-reviewable evidence reference
- explicit per-check results

### 6. Approve Or Reject Stage Readiness

Update:

- [../../../environments/shared/operator-orchestration-service/stage-readiness.yaml](../../../environments/shared/operator-orchestration-service/stage-readiness.yaml)

Stage readiness must stay `pending` unless the current candidate has matching
verification evidence.

### 7. Record Prod Post-Promotion Verification

Because this broker currently runs as one shared control-plane deployment, a
prod-affecting contract change means:

- the shared deployment contract changed
- the prod verification record must be reset or rerecorded

Use:

- [../../../environments/shared/operator-orchestration-service/prod-verification.yaml](../../../environments/shared/operator-orchestration-service/prod-verification.yaml)

The prod verification record must point back to the shared deployment contract
and capture the post-promotion checks from the component-owned prod catalog.

## Evidence Rule

Health endpoints and Argo status are required checks, not sufficient proof.

Every stage or prod verification record must carry:

- exact candidate or contract reference
- operator-reviewable evidence reference
- explicit check results for the component catalog

## Related Control Surfaces

- [README.md](README.md)
- [architecture.md](architecture.md)
- [operations.md](operations.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
