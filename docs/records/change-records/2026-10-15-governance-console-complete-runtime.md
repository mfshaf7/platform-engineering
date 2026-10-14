---
security_evidence:
  review_areas:
    - runtime
    - identity
    - delivery
  findings: []
  risks: []
  workstreams:
    - WS-007
---

# Governance Console Complete Runtime

## Summary

- Date: 2026-10-15
- Short title: Compose the complete local Console runtime
- Environment: `dev-integration`
- Severity: Planned source admission; activation remains Security-gated

## Classification

- Type: product runtime composition and owner-protocol implementation
- User-facing impact: The Console can request bounded Platform operations
  through OOS while Platform supplies one complete startup, health, recovery,
  rollback, cleanup, and teardown lifecycle.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `governance-operations-console`,
  `operator-orchestration-service`, `workspace-governance-control-fabric`,
  `workspace-governance`, and `security-architecture`
- Related ADR: Existing `dev-integration` and Console cross-domain decisions;
  no new component or authority plane is introduced.

## Root Cause

- Immediate failure: OOS implemented the bounded Platform-operation adapter,
  but no authenticated Platform owner endpoint or complete Console runtime
  lifecycle supplied the owner effects.
- Actual root cause: Earlier commissioning paths proved individual Console
  capabilities without one composed Platform lifecycle and exact external
  Security decision binding.
- Why it escaped earlier controls: Individual capability evidence did not
  require the full Console-only idea-to-product runtime to start, recover,
  roll back, tear down, and return to normal availability as one system.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): Pending Agent Gary source commit and protected merge.
- Guardrail added:
  - test: finite catalog, exact command/control binding, replay, failure,
    process-identity recovery, stale marker, credential custody, and rollback
  - validator: Delivery ART evidence-profile bindings for source and live cases
  - runbook: one complete-runtime operator surface
  - ADR: None; the accepted architecture explicitly extends existing control
    planes and the `refinement-catalog` composition.

## Artifact And Deployment Evidence

- Build workflow run: Pending pull request validation.
- Published image tag: None; this local lane uses reviewed source checkouts.
- Published digest: None.
- Recorded prod revision: None; production is outside scope.
- Argo application revision: None; this is local `dev-integration`.

## Host Or Runtime Recovery

- Required host/runtime action: After Security `#1303`, run the complete-runtime
  activation or operating-verification command from the primary runbook.
- Why it was environment drift instead of source defect: Not applicable; this
  is planned source-backed capability work.
- Recovery command or procedure:
  `make governance-console-complete-runtime ACTION=restart`, followed by
  `ACTION=status`.

## Live Verification

- App health: Pending exact-revision composed proof after Security `#1303`.
- Deployed image: Existing reviewed dev-integration source composition.
- Pod: Existing `refinement-catalog` workloads; no new pod or control plane.
- Functional verification: Source tests bind `case:1291-positive` and
  `case:1291-negative`; the final operating command binds
  `case:platform-runtime-positive` and `case:platform-runtime-negative`.
- Residual risk: Runtime activation remains denied until the external Security
  decision accepts the exact Platform candidate tree and every declared owner
  revision.

## Follow-Up

- Required follow-up: Complete Console `#1292`, WGCF `#1294`, Console `#1295`,
  Security `#1303`, protected Platform merge, and the live operating proof.
- Optional hardening: None before the exact accepted composition is proven.
- Owner: `platform-engineering`
