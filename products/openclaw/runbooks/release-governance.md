# OpenClaw Release Governance

## Purpose

This runbook defines how OpenClaw fits the standardized governed release model
while preserving the strongest parts of the existing product flow.

OpenClaw remains the most mature fully governed product in the workspace:

- source pins drive the stage and prod contracts
- a recorded stage candidate is the promotion input
- stage verification is explicit
- stage readiness is explicit
- prod verification is explicit
- prod lifecycle remains a separate bounded control

## Current Release-State Objects

The current OpenClaw release-state objects are:

- [../../../environments/stage/release-candidate.yaml](../../../environments/stage/release-candidate.yaml)
- [../../../environments/stage/verification.yaml](../../../environments/stage/verification.yaml)
- [../../../environments/stage/promotion-readiness.yaml](../../../environments/stage/promotion-readiness.yaml)
- [../../../environments/prod/verification.yaml](../../../environments/prod/verification.yaml)
- [../../../environments/prod/openclaw-lifecycle.yaml](../../../environments/prod/openclaw-lifecycle.yaml)

OpenClaw keeps one explicit retained difference from the generic shared model:

- `environments/stage/promotion-readiness.yaml` is the standardized stage
  readiness decision for OpenClaw, but the product deliberately keeps the
  promotion-oriented filename because that same decision is the hard gate for
  the later `stage -> prod` promotion path

That retained label is intentional and documented. It is not an implicit
exception anymore.

## Verification Catalogs

OpenClaw uses two product-owned verification catalogs:

- [../verification-catalog.yaml](../verification-catalog.yaml)
- [../prod-verification-catalog.yaml](../prod-verification-catalog.yaml)

The stage catalog now uses the standardized `requiredByDefault` flag together
with `acceptedReadinessStatuses` instead of the older product-local
`defaultRequiredForPromotion` field.

## Operator Flow

### 1. Record The Current Stage Candidate

Pin the intended source bundle, build or identify the immutable image digest,
then record the current stage candidate through:

- [record-gateway-image.md](record-gateway-image.md)

This refreshes:

- `environments/stage/release-candidate.yaml`
- `environments/stage/verification.yaml`
- `environments/stage/promotion-readiness.yaml`

### 2. Rehearse The Candidate

Record the exact stage verification evidence in:

- [../../../environments/stage/verification.yaml](../../../environments/stage/verification.yaml)

The current baseline checks come from:

- [../verification-catalog.yaml](../verification-catalog.yaml)

### 3. Record The Stage Readiness Decision

OpenClaw records the standardized stage readiness decision in its retained
product-local file:

- [../../../environments/stage/promotion-readiness.yaml](../../../environments/stage/promotion-readiness.yaml)

Manage that decision through:

- `make openclaw-gateway-readiness ACTION=<status|reset|approve|validate>`
- [../../../.github/workflows/confirm-stage-promotion-readiness.yaml](../../../.github/workflows/confirm-stage-promotion-readiness.yaml)

### 4. Promote The Approved Candidate

Use:

- [promote-stage-to-prod.md](promote-stage-to-prod.md)

Promotion must consume the approved stage candidate and must not rebuild a
second prod-branded artifact for the same source bundle.

### 5. Record Prod Verification

After the prod contract changes, record post-promotion prod verification in:

- [../../../environments/prod/verification.yaml](../../../environments/prod/verification.yaml)

Use:

- [verify-prod-after-promotion.md](verify-prod-after-promotion.md)

### 6. Keep Lifecycle Separate

Prod lifecycle state remains a separate control from release readiness:

- [manage-prod-lifecycle.md](manage-prod-lifecycle.md)
- [../../../environments/prod/openclaw-lifecycle.yaml](../../../environments/prod/openclaw-lifecycle.yaml)

## Evidence Rule

Argo health, bridge health, and gateway reachability are required checks, not
sufficient proof by themselves.

For OpenClaw, governed readiness means the exact candidate, verification
evidence, stage readiness decision, prod lifecycle state, and prod verification
record all remain attributable and current.
