# Temporal

## Purpose

Temporal is the build-admitted platform-owned durable workflow runtime adapter
for workflows whose waits, retries, restarts, reconciliation, or cross-owner
history must survive one request.

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
- profile lifecycle: `build-admitted`
- namespace: none
- Argo application: none
- runtime service: none
- direct operator UI: none
- source artifact pins: Temporal chart `1.2.0`, Temporal `1.31.2`,
  diagnostic UI `2.52.1`, PostgreSQL `17.10-alpine3.24`
- `stage` or `prod` deployment: not approved

The local runtime source and operator commands are implemented, but no runtime
has been installed. Build admission is source authorization, not self-serve
launch or workflow-execution authority.

The source also defines ordered generation retirement: Platform drains ingress
and ordinary pollers, issues the old generation's digest-pinned manifest, and
accepts the receipt from OOS's explicit one-shot worker before a fresh
activation. This contract does not imply that any runtime or retirement run is
currently active.

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

Neither definition is active merely because this component record exists.

## Denied Claims

- Temporal is not an operator-facing business authority.
- WGCF does not own aggregate orchestration.
- OOS is not reduced to a Temporal activity adapter.
- A local dev-integration run is not governed `stage` or `prod` evidence.
- No Console, service, or operator may bypass OOS and invoke Temporal directly.
