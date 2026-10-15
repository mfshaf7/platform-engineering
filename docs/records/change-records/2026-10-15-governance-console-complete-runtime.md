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
- Commit(s): Platform maintenance PR
  [#305](https://github.com/mfshaf7/platform-engineering/pull/305), merged as
  `36510a9783b7b4667e4cdcd60b3144b54515c5f7`, and bounded successor PR
  [#306](https://github.com/mfshaf7/platform-engineering/pull/306), merged as
  `df6844ded120c2325bb09d0b41dacc10fe33a44e`. Platform maintenance PR
  [#307](https://github.com/mfshaf7/platform-engineering/pull/307), merged as
  `e2e664a00fc99c7b4b196b4462db634dbf193d9b`, binds the composed runtime to
  the reviewed Platform worktree unless the operator supplies an explicit
  source override.
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
  - Platform PR
    [#305](https://github.com/mfshaf7/platform-engineering/pull/305)
    landed that repair. Security PR
    [#254](https://github.com/mfshaf7/security-architecture/pull/254)
    accepted its exact Platform tree
    `79539f1e3ffc0c0dadf8f4dac2c4cef1b21f9842` without widening the trust
    boundary.
  - successor session
    `work-session:delivery-1275:delivery-1275-platform-composition:r2` starts
    from the reviewed repair commit and owns the repeated merge-ready and live
    operating proof.
  - the governed `r2` operating acquisition exposed a source-selection
    conflict before activation: the complete-runtime verifier executed from
    the reviewed Platform PR worktree while the shared composition runner
    defaulted the Platform source dependency to the workspace `main` checkout.
    The verifier now passes its own current Platform checkout explicitly to
    composition and cross-domain commands, while an explicit operator
    `--repo-path` still takes precedence. A focused regression test covers
    both paths.
  - Platform PR #307 landed that repair. The failed `r2` attempt was archived
    with its own preserved evidence and is not represented as successful
    operating proof.
  - governed successor session
    `work-session:delivery-1275:delivery-1275-platform-composition:r3` starts
    from merged Platform revision
    `e2e664a00fc99c7b4b196b4462db634dbf193d9b` and owns the final exact-head
    Security acceptance and live operating proof.

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

- Required follow-up: Review this bounded successor revision, bind an external
  Security decision to its exact PR head and tree, then run the live operating
  proof from governed session `r3`. Platform PRs #305, #306, and #307 remain
  immutable repair and recovery evidence. Console `#1292`, WGCF `#1294`, and
  Console `#1295` remain exact-revision inputs to that proof.
- Optional hardening: None before the exact accepted composition is proven.
- Owner: `platform-engineering`
