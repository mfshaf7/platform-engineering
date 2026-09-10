# Prototype Maturity Identity Definition

## Summary

- Date: 2026-09-10
- Short title: Selected, inactive Prototype Maturity source identity
- Environment: Source-only definition for `dev-integration`
- Severity: Planned capability, not an incident

## Classification

ART #1128 under #920/#892; source Landing Unit
`delivery-892-prototype-maturity-identity-definition`. No provider, secret,
cluster, workflow, or runtime activation is included.

## Ownership

Platform owns identity definition, secret custody, commissioning, suspension,
revocation, and rollback. OOS owns workflow and source coordination. Prototype
Studio owns canonical maturity state. WGCF owns readiness. Security #1125 owns
the normal-availability decision. Related decision:
[ADR-027](../../decisions/adr/ADR-027-dedicated-prototype-maturity-identity.md).

The concrete Security authority is the accepted-with-findings
[Prototype Maturity Trust-Boundary Review](https://github.com/mfshaf7/security-architecture/blob/61c96e53cf87491e8d42ba076fa241844b5132e5/docs/reviews/components/2026-09-09-prototype-maturity-trust-boundary.md).
The definition also pins the applicable Identity and Access, Secrets and
Recovery, and GitOps and Machine Trust sources at Security Architecture
revision `2814c54542e020913af37c5805f953ec18864e05`. This prior review permits
inactive implementation only; it does not replace final gate #1125.

## Root Cause

Prototype Maturity source and conformance work is complete, but its normal path
cannot safely reuse the commissioned Prototype Landing identity. The two
workflows have different branch, path, audit, revocation, and rollback scopes.

## Source Changes

Added the exact-repository inactive identity contract, strict schema, read-only
validator, filesystem conformance tests, and primary operator documentation.
Validation rejects Landing identity reuse, broader permissions or paths,
premature activation, ambient credentials, secret disclosure, and rollback
that could affect the Landing identity.

## Artifact And Deployment Evidence

Owner validation and the finalized Review Packet bind the exact contract digest
and source head. No image, live App, installation, token, Vault value, Secret,
deployment, or runtime availability is claimed.

## Host Or Runtime Recovery

None. This work changes source definitions only.

## Live Verification

Read-only validation proves deterministic parsing, exact scope, negative
contract cases, restoration, and secret-safe failure output. Provider and
runtime proofs are intentionally deferred to #1131 after Security, WGCF, and
OOS activation prerequisites land.

## Follow-Up

Security #1125 reviews this exact source. #1129 through #1132 own readiness,
orchestration, commissioning, and operating proof. Revert this source unit
independently without changing Prototype Landing or any active runtime.
