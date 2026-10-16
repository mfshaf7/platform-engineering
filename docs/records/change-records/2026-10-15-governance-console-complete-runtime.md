---
security_evidence:
  review_areas: [identity, secrets, runtime, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Governance Console Complete Runtime

## Summary

Maintenance Landing Unit `maintenance-1275-workflow-credential-lifecycle-platform`
uses `child_isolated_landing_unit` for the operator-approved extension of the
existing renewal timer and readiness checks. The real Console journey found
expired Proposal Target, Landing, Maturity, Closure and Intake tokens even
though complete-runtime activation passed. This repair rotates the five
already-enabled dedicated Apps through existing identity validation, preserves
owner configuration and unrelated Secret fields, batches token consumption
into one OOS rollout, and proves actual mounted-token/provider acceptance.
It introduces no service, permission, credential authority or ART child.

Merge Platform first, refresh the existing Security exact-composition decision
and generated change-record index second, then activate and prove all five
identities. Exact-revision consumers are that Security decision and its private
materialized policies; no OOS, Console, WGCF or Workspace Governance source
change is planned. Rollback stops renewal but preserves the pre-existing five
owner bindings; it still revokes the Console-owned provisioning/provider
credentials. Source tests are not live proof. The final acceptance still needs
the real persistent to-do product and Portfolio readback.

Bootstrap preflight found two absent declared Vault entries and one invalid
stored Maturity PEM. Proposal Target and Closure were imported create-only
from the existing operator keys. Maturity's existing valid private key was
verified against its exact App and installation, then updated with Vault
version compare-and-swap; prior Vault version 2 remains recoverable. All five
Vault keys, App identities, installations and existing permissions passed
read-only provider verification before activation. No App permissions or
repository selection changed. Batch preparation now validates all replacement
grants before changing the first runtime Secret; its invalid-later-key test
proves that earlier prepared grants are revoked without partial delivery.

Maintenance Landing Unit `maintenance-1275-runtime-probe-contract` uses
`child_isolated_landing_unit` for the Platform verification-only correction.
Live Console GET returned HTTP 404 with its documented public adapter code
`repository_custody_oos_rejected` and the exact missing-request message, but
the Platform checker expected OOS's internal error representation. The checker
now validates the actual Console boundary, rejects route/identity/preview
lookalikes, and waits at most thirty seconds for tunnel recovery after the
already approved OOS rollout. This changes no identity, mutation, delivery,
credential, source-acceptance, or rollback authority. The Console API is unchanged.

The same maintenance Landing Unit includes automatic purpose-bound repository
credential renewal through the existing local systemd lifecycle. Five-minute
checks renew before expiry, reconcile the exact non-secret delivery version
into OOS, and stop before rollback revocation. Lifecycle locking, stale-source
denial, interrupted-consumption recovery, and exact operating-proof receipt
binding cover that continuation; activation-only delivery is not represented
as unattended readiness.

- Date: 2026-10-15
- Short title: Compose the complete local Console runtime
- Environment: `dev-integration`
- Severity: Planned source admission; activation remains Security-gated

## Classification

- Maintenance Landing Unit: `maintenance-1275-complete-runtime-repository-custody`.
- Landing Unit Decision: `child_isolated_landing_unit`; one Platform runtime
  repair, review, deployment, and rollback boundary, tracked by this existing
  record and the Epic 1275 acceptance exercise without a new ART child.
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
  The first complete-runtime proof then repeated that narrow boundary by
  validating Platform-operation recovery without asserting each terminal
  capability required by the downstream to-do acceptance journey.

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
  - the `r3` proof then exposed a self-hosting boundary: full composition
    teardown terminated the source executor process group supervising that
    proof before it could retain the result. OOS PR
    [#339](https://github.com/mfshaf7/operator-orchestration-service/pull/339)
    moves runtime/live evidence into its own process group, and OOS PR
    [#340](https://github.com/mfshaf7/operator-orchestration-service/pull/340)
    permits the existing evidence-preserving recovery path to archive an
    interrupted acquisition without claiming readiness.
  - the failed `r3` attempt is archived with its exact merge-ready packet. The
    `r4` successor serializes the complete proof with an operator-private file
    lock and reuses only a digest-valid receipt bound to the exact current
    Security decision, reviewed revisions, complete proof shape, and restored
    normal availability. This lets the detached original proof restore the
    runtime and lets the replacement executor reconcile that exact result
    without repeating teardown.
  - the fixture-free item `#1298` acceptance journey then exposed that the
    complete-runtime proof was still narrower than its downstream contract:
    Repository Control correctly failed closed because the coordinator had not
    delivered the approved provisioning identity, activated WGCF repository-
    custody readiness, enabled persistent OOS custody state, or projected the
    required Console authority references. The maintenance repair composes
    those existing controls into the same lifecycle and makes `status` fail
    unless Console repository provisioning is executable end to end.
  - activation and restart now mint a fresh short-lived token through the
    existing Vault-backed provisioning identity tool. Rollback revokes that
    token and removes its Secret before removing OOS and WGCF bindings. The
    private key and token remain absent from source, process arguments,
    receipts, and browser state.
  - a subsequent host restart exposed that cleanup had removed a Platform
    worktree still referenced by composition auto-resume and provider systemd
    units. Recovery rebound the units to main. The coordinator now chooses
    the surviving clean main checkout for persistent service commands only
    when its tree matches both the reviewed worktree and `origin/main`.
    Tests retain the worktree when either checkout is dirty, and the primary
    runbook requires service-source verification before worktree retirement.

## Artifact And Deployment Evidence

- Build workflow run: The original `r4` proof is complete. The repository-
  provisioning maintenance PR and exact-tree Security refresh are pending.
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

- App health: The prior exact-revision composed proof passed for the Platform-
  operation boundary. Repository provisioning remains unproven until the
  maintenance source is reviewed, Security refreshes the exact Platform tree,
  and the repaired operating proof and item `#1298` browser journey pass.
- Deployed image: Existing reviewed dev-integration source composition.
- Pod: Existing `refinement-catalog` workloads; no new pod or control plane.
- Functional verification: Source tests bind `case:1291-positive` and
  `case:1291-negative`, including exact cached-receipt reuse and stale or
  malformed receipt rejection; the final operating command binds
  `case:platform-runtime-positive` and `case:platform-runtime-negative`.
- Residual risk: Runtime activation remains denied until the external Security
  decision accepts the exact Platform candidate tree and every declared owner
  revision.

## Follow-Up

- Required follow-up: Review the bounded repository-provisioning maintenance
  revision, refresh the external Security decision against its exact Platform
  head and tree, run the repaired complete-runtime operating proof, and then
  complete the real item `#1298` Console journey. Platform PRs #305 through
  #310 remain immutable repair and recovery evidence. Console `#1292`, WGCF
  `#1294`, and Console `#1295` remain exact-revision inputs to that proof.
- Optional hardening: None before the exact accepted composition is proven.
- Owner: `platform-engineering`


## Canonical Repository Gate Maintenance — 2026-10-16

### Summary

- Date: 2026-10-16
- Short title: Bounded Proposal Repository resolution recovery
- Environment: dev-integration contract only
- Severity: acceptance-blocking maintenance for #1275 / #1298

### Classification

- Type: source contract extension
- User-facing impact: retain the exact Repository gate receipt and replay inputs
  so browser reload after partial acknowledgement does not require CLI repair.
- Landing Unit Decision: child_isolated_landing_unit; Platform owns the canonical
  storage contract consumed by OOS. No new ART child or storage service.

### Ownership

- Owning repo or layer: platform-engineering, OpenProject state contract
- Related repos: operator-orchestration-service, governance-operations-console
- Related ADR: None; bounded extension of the existing machine-state field.

### Root Cause

- Immediate failure: live Proposal Repository gate had only local resolution.
- Actual root cause: missing canonical handoff and recoverable acknowledgement.
- Why it escaped earlier controls: isolated capability checks omitted the full
  handoff and interrupted-browser recovery.

### Source Changes

- Repo: platform-engineering
- Commit(s): candidate source; not operating evidence
- Guardrail added: optional bounded typed current resolution, compatible with
  existing records. OOS validates the same shape; immutable history remains in
  OpenProject journals, not an accumulating state-field log.

### Artifact And Deployment Evidence

- Build workflow run: None
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None
- Exact-revision consumers: complete-runtime Security acceptance requires
  refreshed Platform source binding before activation; OOS mirror must land
  after this contract. Console source and current acceptance also need refresh.

### Host Or Runtime Recovery

- Required host/runtime action: None for the optional schema itself.
- Why it was environment drift instead of source defect: not environment drift.
- Recovery command or procedure: existing complete-runtime activation after
  the accepted OOS and Console repair batch; do not mutate canonical records here.

### Live Verification

- App health: existing composed runtime remains available.
- Deployed image: unchanged by this source candidate.
- Pod: None changed.
- Functional verification: validation pending; optional-field compatibility and
  OOS mirror equivalence must pass before merge.
- Residual risk: does not itself prove the Console handoff operational.

### Follow-Up

- Required follow-up: OOS and Console source validation, exact Security delta
  acceptance, ordered activation and real browser journey.
- Optional hardening: None added.
- Owner: platform-engineering and the existing workflow owners.

Security review boundary: the existing [controlled Console runtime review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-15-governance-console-platform-operation.md) must accept the exact repair sources before activation. This source candidate is not operating acceptance.
