# Governance Console Session Projection

## Summary

- Date: 2026-09-27
- Short title: Platform identity and session projection for the Governance Operations Console
- Environment: Local `dev-integration` source and contract proof only
- Severity: Planned capability, not an incident

## Classification

ART #1179 under #898. This Landing Unit records the Platform implementation
that supplies display-safe operator identity and session truth to the
Governance Operations Console. It does not activate Console enforcement,
approve the combined trust boundary, or claim stage or production readiness.

## Ownership

Platform owns projection policy, issuance, inspection, revocation, and the
underlying admitted `dev-integration` session truth. The Console owns
consumption and route enforcement. OOS owns workflow authorization and
mutation attribution. Security Architecture owns approval of the combined
boundary.

## Root Cause

The Console had no stable Platform-owned source for operator identity, role,
named authority, session binding, or expiry. Supplying that context from local
UI fixtures or browser state would make future authorization and attribution
unreliable.

## Source Changes

Platform PR #248 added the Console product integration contract, strict policy
and schema, projection operator, tests, validation wiring, stable
`dev-integration` session start time, and the owner evidence profile used by
the normal OOS work-session path.

- Implemented head: `ed45224f27e3a32103beecb6f4ff33d74816d9c6`
- Merged revision: `f4475dbd0129961302ff48aea10b751b6b85512a`
- Architecture packet: `wgcf://artifacts/delivery-art/sha256/5baddcf4c20bcf1a472074dfdb1a537a0f87e8aedf8504adbf75ff14d72eaa5c`

The projection is private, non-secret, atomically written with mode `0600`,
bound to one admitted operator and active session, and limited to eight hours.
Missing, stale, conflicting, stopped, or unadmitted session truth fails closed.

## Artifact And Deployment Evidence

PR #248 passed the exact-head repository validation and posture checks before
human approval and squash merge. No image, Argo revision, stage deployment, or
production deployment was created by this work.

## Host Or Runtime Recovery

Use the product runbook to revoke the local projection. The Console must then
fail closed until Platform issues a fresh projection from an active admitted
session. No credential or browser authority is reconstructed from this record.

## Live Verification

Repository tests cover issuance, inspection, revocation, stable session
binding, owner and mode checks, expiry, conflicting sessions, invalid policy,
and fail-closed session states. This evidence proves the local Platform
contract only. Console enforcement remains #1180 and Security activation
remains #1181.

## Follow-Up

- #1180: consume and enforce the projection in Console source.
- #1181: review and approve the combined Platform, Console, and OOS boundary.
- #929 and #930: prove the admitted end-to-end operating path after those
  prerequisites land.
