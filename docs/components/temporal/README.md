# Temporal

## Purpose

Temporal is the platform-owned durable workflow runtime adapter for workflows
whose waits, retries, restarts, reconciliation, or cross-owner history must
survive one request. Its source profile is active only for admitted local
`dev-integration` OOS workflow compositions; runtime activation is separately
proof-gated.

Temporal does not own business workflow policy. `operator-orchestration-service`
owns aggregate workflow definitions, run control, correlation, projections,
and final orchestration receipts.

## Start Here

- [architecture.md](architecture.md)
- [access.md](access.md)
- [operations.md](operations.md)
- [release-governance.md](release-governance.md)
- [ADR-017: Temporal Durable Workflow Runtime](../../decisions/adr/ADR-017-temporal-durable-workflow-runtime.md)
- [Security build admission](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-07-31-temporal-durable-orchestration-build-admission.md)

## Current Live Footprint

- intake classification: `proposed`
- dev-integration profile: `temporal`
- source profile lifecycle: `active`
- live namespace: absent until the merged-runtime proof owned by ART #1020
- Argo application: none
- runtime service: none
- direct operator UI: none
- source artifact pins: Temporal chart `1.2.0`, Temporal `1.31.2`,
  diagnostic UI `2.52.1`, PostgreSQL `17.10-alpine3.24`
- `stage` or `prod` deployment: not approved

The local runtime source and operator commands are implemented. Normal launch
is governed by the shared dev-integration runner and the registered
`refinement-catalog` composition after Workspace binding #1019 and merged
runtime proof #1020. Active source lifecycle is not a live-runtime, stage,
production, or direct business-workflow claim.

The source also defines ordered generation retirement: Platform drains ingress
and ordinary pollers, issues the old generation's digest-pinned business-queue
and start-registry manifest with a pinned OOS receipt verifier, and accepts the
Ed25519-attested exact-reconciliation receipt from OOS's explicit one-shot
worker before a fresh activation. This contract does not imply that any runtime
or retirement run is currently active.

The source registers `delivery.refinement.apply` version `1` as the first
selected OOS-owned business workflow for the `refinement-catalog` composition.
The registration binds the versioned OOS contract to composition-scoped queue,
worker, and activation evidence. It does not expose Temporal credentials or
authorize Console access.

## Owner Boundaries

- `workspace-governance` owns durable-orchestration authority and admission
  contracts.
- `operator-orchestration-service` owns aggregate workflow behavior and the
  runtime adapter boundary.
- `platform-engineering` owns Temporal runtime topology, persistence,
  lifecycle, access, observability, and promotion.
- domain services own their bounded, idempotent workflow activities.
- `security-architecture` owns trust-boundary review and security acceptance.
- Governance Operations Console calls OOS and never calls Temporal directly.

## Initial Proof Order

1. `validation-readiness-run`
   - safe runtime and restart proof
   - bounded WGCF readiness activity
2. `delivery.refinement.apply`
   - first business workflow after runtime admission

The business definition is usable only while its admitted composition and
activation evidence are current.

## Denied Claims

- Temporal is not an operator-facing business authority.
- WGCF does not own aggregate orchestration.
- OOS is not reduced to a Temporal activity adapter.
- A local dev-integration run is not governed `stage` or `prod` evidence.
- No Console, service, or operator may bypass OOS and invoke Temporal directly.
