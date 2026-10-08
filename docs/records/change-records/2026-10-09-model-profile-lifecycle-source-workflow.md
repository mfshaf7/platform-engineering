# Model-Profile Lifecycle Source Workflow

## Summary

- Date: 2026-10-09
- Short title: Source-backed model-profile lifecycle application and readback
- Environment: source and disposable local proof only
- Severity: planned delivery

## Classification

- Type: platform contract and operator workflow extension
- User-facing impact: reviewed Model Operations requests can reach exact
  Platform source application, projection, merged readback, and rollback
  without granting OOS or Console registry authority.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`,
  `governance-operations-console`, `security-architecture`
- Related ADR: ADR-012

## Root Cause

- Immediate failure: the registry had validation and runtime resolution but no
  source-backed consumer for the OOS model-profile lifecycle request contract.
- Actual root cause: request/review authority, Platform source authority, and
  merged readback had not yet been joined by a typed handoff.
- Why it escaped earlier controls: earlier profiles were landed directly as
  reviewed source changes before the Model Operations workflow existed.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): recorded by the finalized ART #1241 Review Packet
- Guardrail added:
  - exact OOS contract source lock
  - Platform decision, receipt, and projection schemas
  - source application/readback/restore command
  - positive and negative protocol and disposable operating tests
  - verification-only live OOS/Console operating-evidence command
  - primary operator procedure

## Artifact And Deployment Evidence

- Build workflow run: recorded by the ART #1241 Review Packet
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

None. This change does not activate a profile, provider, caller, service, or
runtime. Security ART #1243 remains the activation gate.

## Live Verification

- App health: not applicable
- Deployed image: not applicable
- Pod: not applicable
- Functional verification: disposable source copies prove approved application,
  current projection, clean merged readback, exact restore, and all planned
  denial cases without changing the canonical registry.
- Residual risk: a real new caller remains unavailable until its exact Security
  decision and Platform runtime activation are complete.

## Follow-Up

- Required follow-up: ART #1242 consumes the Platform projection/readback;
  ART #1243 records Security acceptance before activation.
- Optional hardening: None required for this source boundary.
- Owner: `platform-engineering`
