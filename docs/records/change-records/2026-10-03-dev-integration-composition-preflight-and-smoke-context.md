# Dev-Integration Composition Preflight And Smoke Context

## Summary

- Date: 2026-10-03
- Short title: Fail before composition mutation and preserve smoke context
- Environment: local `dev-integration`
- Severity: corrective owner-repo maintenance

## Classification

- Type: host/environment drift and rollout-evidence control
- User-facing impact: composition startup now rejects missing source
  dependencies, unsafe runtime custody, unavailable login recovery, and pending
  Helm operations before mutation; profile smoke no longer reports active
  composed dependencies as inactive.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `workspace-governance`, `operator-orchestration-service`,
  `security-architecture`, and profile owner repositories
- Related ADR: None; this extends the existing shared dev-integration runner.

## Root Cause

- Immediate failure: repeated composition rehearsals reached child mutations
  before late source, host, systemd, and Helm failures, while standalone smoke
  omitted the active composition identifier.
- Actual root cause: the runner had no composition-wide prerequisite boundary
  before `execute_composition`, and its profile smoke path accepted only ambient
  composition variables supplied by composition dispatch.
- Why it escaped earlier controls: profile validation proved contracts and
  per-profile status, but no control joined source readiness, host restart
  readiness, cluster transaction state, and active smoke context at the shared
  runner boundary.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): this Landing Unit and its pull request
- Guardrail added:
  - deterministic preflight and active-context unit tests
  - preflight cases imported by the existing composition-test CI entrypoint,
    preserving Agent Gary's no-workflow-write least-privilege boundary
  - non-mutating composition preflight before credential or profile mutation
  - fail-closed active-context discovery for profile smoke
  - exact Workspace operations source-pin refresh needed to rotate the expired
    short-lived GitHub App token exposed by the stronger smoke
  - primary operator runbook updates

## Artifact And Deployment Evidence

- Build workflow run: owner-repository CI-equivalent validation in the pull request
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: rotate the expired Workspace operations token
  through the exact-source identity operator, rerun the normal composition
  `up`, and run profile smoke after merging the runner change.
- Why it was environment drift instead of source defect: the original crashes
  exposed root-owned runtime state, an unavailable user manager, and an
  interrupted Helm transaction; the source defect was the runner's failure to
  detect those conditions before mutation.
- Recovery command or procedure: follow
  [Dev-Integration Profiles](../../runbooks/dev-integration-profiles.md).

## Live Verification

- App health: branch-bound composition status passed after the distinct OOS
  smoke credential repair; exact-source identity status passed after token
  rotation, and composition-aware smoke read 28 Inventory records from
  Workspace Governance revision `c41724986ca1290029555010d9a252f869434c6c`
- Deployed image: existing profile-owned local runtime images
- Pod: existing `refinement-catalog` participant workloads
- Functional verification: unit regressions; branch-bound composition
  preflight and status passed. The stronger smoke first exposed an unbound OOS
  caller, then the existing distinct-secret invariant, and finally the expired
  Workspace operations token. Each layer failed closed. Approved token
  rotation then passed direct identity status and the normal context-aware
  read-only smoke. Final completion still requires final-head host-service
  reconciliation and the same proof from merged `main`.
- Residual risk: the preflight detects pending Helm transactions but does not
  automatically repair them; operator review remains required before retry.

## Follow-Up

- Required follow-up: close the linked Workspace Governance improvement
  candidate through an after-action after merged-main live proof.
- Optional hardening: add profile-declared dependency probes if a future
  host-service runtime cannot be verified by its owner dependency manifest.
- Owner: `platform-engineering`
