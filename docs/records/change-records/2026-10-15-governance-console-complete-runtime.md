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
    process-identity recovery, stale marker, credential custody, read-only
    workspace-continuity enablement, and rollback
  - validator: Delivery ART evidence-profile bindings for source and live cases
  - runbook: one complete-runtime operator surface
  - ADR: None; the accepted architecture explicitly extends existing control
    planes and the `refinement-catalog` composition.
- Recovery correction:
  - OOS PR
    [#338](https://github.com/mfshaf7/operator-orchestration-service/pull/338)
    permits the replacement work session to execute only the nearest
    qualifying reviewed ancestor profile when the accepted base profile is
    invalid, while candidate and accepted-head validation remain mandatory.
  - replacement session
    `work-session:delivery-1275:delivery-1275-platform-composition:r1`
    corrects the complete-runtime operating-verification timeout from `3600`
    to the schema maximum `1800` seconds.
  - the first live replacement proof exposed two precondition gaps that source
    tests had not exercised: OOS ran as UID 1000 without a writable volume at
    the injected Platform-operation state path, and rollback waited for OOS
    readiness before removing the binding that caused the startup failure.
    The maintenance repair now projects a mode-0700 operator-private host
    directory into the exact OOS state path and removes the OOS environment
    and state binding before cross-domain rollback waits for readiness.
  - the preserved merge-ready packet and archived failed attempt remain bound
    to Platform PR #303; they are not represented as evidence for this
    replacement source revision.

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

- Required follow-up: Merge the writable-state and rollback-order maintenance
  repair, obtain the fresh Security delta for that exact Platform tree, recover
  the failed replacement attempt through the evidence-preserving path, and run
  the live operating proof from its governed successor. Console `#1292`, WGCF
  `#1294`, and Console `#1295` remain exact-revision inputs to that review.
- Optional hardening: None before the exact accepted composition is proven.
- Owner: `platform-engineering`
