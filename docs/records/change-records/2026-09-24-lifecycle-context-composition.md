# Lifecycle Context Composition Commissioning

## Summary

- Date: 2026-09-24
- Short title: Controlled local OOS-to-CGG lifecycle context composition
- Environment: operator-scoped local `dev-integration`
- Severity: planned capability, not an incident

## Classification

ART #1167 under #1159/#892 commissions the bounded runtime composition approved
by Security. It does not activate stage, production, release, model, approval,
or lifecycle-mutation authority.

## Ownership

Platform owns composition validation, ephemeral credential projection,
activation, status, proof, rotation, suspension, teardown, and rollback. OOS
owns lifecycle request handling. CGG owns context admission and projection.
The Console remains an OOS client and receives neither a CGG route nor the
lifecycle caller credential.

## Root Cause

OOS and CGG had independently admitted local profiles and reviewed context
contracts, but no Platform-owned composition safely joined them. Without this
work, activation depended on manual runtime mutation with no bounded rotation,
teardown, rollback, or end-to-end operating proof.

## Reviewed Boundary

- Security decision revision: `51be54e6bfa7759589ca4960fe9ef34def7f5dd8`
- CGG selected and reviewed revision: `f57423379aceb28d0072b977e43ee0f18590ae20`
- OOS reviewed baseline: `041f167dfbb19c0da0b12707b035a4fa36ad96d9`
- OOS selected revision: `0a5d1bf3a0cfe7e731d70f88bd71edb47b3e6cab`

The selected OOS revision descends from the reviewed baseline and adds the
merged null-safe credential-reference persistence correction. It does not
widen the lifecycle-context API, caller, or authority boundary.

## Source Changes

Added one Platform-owned composition definition, controller, tests, Make
entrypoint, primary operator procedure, and component guidance. The controller
uses the existing admitted OOS and CGG profiles, projects only declared
lifecycle variables, generates a new caller secret for every activation, and
stores only its digest in private local state and receipts.

## Artifact And Deployment Evidence

This change creates no image, chart, Argo application, stage deployment, or
production deployment. The finalized Review Packet binds the merged Platform
source revision and the exact local composition evidence.

## Live Verification

Controlled proof covered:

- activation and readiness
- packet projection and identical replay
- conflicting replay and invalid-request denial
- explicit reasoned raw fallback with measurements
- CGG loss and OOS fail-closed behavior
- OOS and CGG restart with replay preservation
- caller credential rotation
- suspension, teardown, rollback, and reactivation
- lifecycle secret absence after each stop action

The finalized Review Packet binds the exact source head and private,
secret-free runtime receipts. No credential value is included in Git, command
arguments, durable state, receipts, or ART evidence.

## Recovery

Run `make lifecycle-context ACTION=rollback`. Rollback removes only the
lifecycle-specific environment and secrets, verifies OOS denies new context
requests, and preserves the participant profiles, ART, Git, work-session state,
CGG custody, and unrelated CGG routes. Re-run `up` and `smoke` to recommission.

## Residual Boundary

This is local `dev-integration` evidence only. Any stage or production use,
direct Console-to-CGG route, additional caller, broader credential projection,
or authority change requires a new Platform and Security decision.

## Follow-Up

None is required for the local commissioning boundary. Any wider lifecycle use
must enter ART as separately reviewed work rather than extending this binding
implicitly.
