# Workspace Intake And Active Inventory Dev-Integration Commissioning

> Correction: this commissioning claim is invalidated. The recorded Console
> activity checks proved only the Console's OOS/WGCF read boundary; they did
> not configure or directly probe Workspace Intake or Inventory. This record is
> retained as audit history and must not be used as operating evidence.

## Summary

- Date: 2026-10-02
- Short title: Commission the reviewed Intake and Inventory composition
- Environment: local `dev-integration`
- Severity: invalidated activation evidence

## Classification

- Type: product integration and runtime composition
- User-facing impact: none was proven for Workspace Intake or Active Inventory.
  The Console read boundary remained a separate capability.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `workspace-governance`,
  `workspace-governance-control-fabric`, `operator-orchestration-service`,
  `governance-operations-console`, and `security-architecture`
- Related ADR: None; this extends the existing approved loopback-only Console
  composition rather than creating a new control plane or trust boundary.

## Root Cause

- Immediate gap: OOS was launched without the Intake/Inventory enable flags,
  WGCF endpoints and caller bindings, authority/state mounts, or dedicated
  Workspace Governance identity projection.
- Actual root cause: commissioning reused the Console cross-domain activity
  script and treated generic `/api/governance-activity` success as capability
  proof. That script never inspected the required OOS/WGCF configuration or
  called the Intake and Inventory routes.
- Why it escaped earlier controls: the completion evidence asserted the target
  capability without a capability-specific authenticated probe.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): the `delivery-1203-intake-inventory-platform` Landing Unit and its
  finalized Review Packet
- The original guardrails were insufficient:
  - exact current and predecessor architecture-packet binding
  - exact Security review and owner-revision binding
  - explicit clean-worktree source selection without disturbing preserved local state
  - secret-free architecture and credential-boundary receipts
  - the claimed commissioning, denial, restart, rollback, revocation, and
    teardown procedure exercised only the Console read boundary

Corrective maintenance adds a fail-closed Workspace operations identity
`status` action with authenticated direct Intake preparation and Inventory
registry probes, exact shared authority-revision binding, live runtime
configuration checks, and invalid-caller denial. Activation remains blocked
until refreshed Security acceptance is pinned.

Approved input revisions:

- Workspace Governance: `e3864940dd6961426de93fa5cdb2215a86a5aca1`
- WGCF: `0d0b686ea78397d91f64b498d78a4aa6651e1c05`
- OOS: `ce061b456c44f52d327908729db3b1e934f26acf`
- Console: `d17912691a6dd99335c327637eda98c4105d98eb`
- Security: `a214817f50f8991938f2f3059da52e490c589cda`

Architecture lineage:

- current: `sha256:e31fd8cc44410fe88f1ee58f68944fe7a460c637e1d9396dc66290387a4af1fe`
- predecessor: `sha256:34022576c3cbcff6e3bf09d2ac0f5689e1b2255e82cc02a1233970b7fdc03bbe`
- relationship: exact supersession accepted by the pinned Security review

## Artifact And Deployment Evidence

- Build workflow run: owner-repository CI-equivalent validation in the Review Packet
- Published image tag: owner profile images generated from the exact approved source revisions
- Published digest: not applicable to the local Console process
- Recorded prod revision: None
- Argo application revision: None
- Invalidated Console read-boundary receipts: retained under the operator-private
  `governance-console-cross-domain/receipts` directory and referenced by the
  Landing Unit runtime evidence. Each receipt records the exact executing
  Platform commit, architecture lineage, approved owner revisions, and
  secret-free credential boundary. They are not Workspace operations receipts.

## Host Or Runtime Recovery

- Required host/runtime action: reconcile the existing `refinement-catalog`
  owner profiles at the exact approved revisions, then activate the
  loopback-only Console composition.
- Recovery procedure: follow
  [Activate cross-domain awareness](../../../products/governance-operations-console/runbooks/activate-cross-domain-awareness.md).

## Live Verification

- App health: Console activity reported both OOS and WGCF as current through
  the loopback-only live owner path; this did not prove Intake or Inventory.
- Credential boundary: the Console environment remained operator-private mode
  `0600`; browser credentials remained prohibited; the dedicated WGCF reader
  binding was present only while the composition was active.
- Functional verification: Console activation, status, restart, deliberate WGCF
  disconnection without fixture fallback, recovery, bounded rollback,
  credential revocation, cleanup, final activation, and final status passed for
  the Console read boundary only. Workspace operations verification did not.
- Rollback verification: Console services and the WGCF reader binding were
  absent while owner profile sessions and data remained present; cleanup also
  removed private runtime files while retaining the receipts.
- Residual risk: single local operating-system account remains the human trust
  root; shared, remote, stage, and production use remain unapproved.

## Follow-Up

- Required follow-up: land the source repair under owner-repo maintenance,
  obtain refreshed exact-revision Security acceptance, then run the bounded
  composition, identity delivery, direct authenticated status, denial,
  revocation, rollback, and cleanup proof. No replacement ART item is required.
- Owner: `platform-engineering`
