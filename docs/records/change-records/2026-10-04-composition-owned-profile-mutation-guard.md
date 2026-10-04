# Composition-Owned Profile Mutation Guard

## Summary

- Date: 2026-10-04
- Short title: Preserve active runtime-composition bindings
- Environment: local `dev-integration`
- Severity: corrective owner-repo maintenance

## Classification

- Type: dev-integration lifecycle control
- Recommendation posture: `extend`
- Work home: owner-repo maintenance linked to the accepted Workspace
  Governance improvement candidate
- Landing Unit decision: `child_isolated_landing_unit`; this Platform runner
  guard is independently reviewable and reversible from the OOS evidence
  executor repair.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service` and `workspace-governance`
- Existing control extended: shared dev-integration runtime-composition runner
- Tracking reference:
  `workspace-governance/reviews/improvement-candidates/2026-10-04-work-session-merge-order-recurrence.yaml`

## Root Cause

- Immediate failure: a direct `accepted-idea-delivery` profile `up` ran after
  the `refinement-catalog` composition was active and replaced its
  composition-only Catalog bindings.
- Actual root cause: profile lifecycle actions trusted the caller to remember
  composition ownership even though the current profile manifest already
  recorded that ownership.
- Why it escaped earlier controls: the composition runner projected binding
  context into child actions, but the standalone profile path never compared
  its mutation request with the existing composition-owned session.

## Source Changes

- Direct profile `up`, `down`, `reset`, and `restore` fail closed while the
  recorded owning composition is active, degraded, or unavailable.
- Composition-dispatched child actions remain valid only when their composition
  and root-profile context match the existing profile manifest.
- A suspended composition permits profile-specific `reset` or `restore`, while
  profile `up` still routes back through the owning composition.
- The generic CI-based commissioning fallback is removed. The reviewed
  evidence profile already invokes the explicit non-disruptive
  `verify-commissioning` action.

## Artifact And Deployment Evidence

- Build workflow run: owner-repository CI-equivalent validation in the pull request
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Live Verification

- Unit tests cover direct active-composition denial, exact child-context
  admission, read-only status, suspended reset/restore, and the explicit
  evidence-profile verifier command.
- After merge, reconcile `refinement-catalog` from merged owner revisions and
  prove both composition status and accepted-delivery status.

## Residual Risk

The guard is a local operator safety control, not a privilege boundary. The
operator owns the local runtime and state, while the recorded manifest and
composition lifecycle provide the authoritative workflow routing signal.

## Follow-Up

- Link the merged Platform and OOS controls in the improvement after-action.
- Reconcile the active composition from merged `main` revisions before
  declaring the repair complete.

## Rollback

Revert the runner guard, regression tests, runbook clarification, tactical
commissioning fallback removal, and this record together. Restore the complete
composition immediately after rollback so profile-only activation does not
remain in service.
