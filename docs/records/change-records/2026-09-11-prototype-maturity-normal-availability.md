# Prototype Maturity Normal Availability

## Summary

- Date: 2026-09-11
- Short title: Commission Prototype Maturity runtime availability
- Environment: `dev-integration`
- Severity: Planned capability activation, not an incident

## Classification

ART #1131 under #920/#892; source Landing Unit
`delivery-892-prototype-maturity-activation-platform`. This record covers the
Platform-owned identity commissioning, runtime composition, and recovery
boundary. Console-path operating proof remains owned by #1132.

## Ownership

Platform owns private-key custody, short-lived token delivery, runtime
projection, gate composition, suspension, revocation, and recovery. OOS owns
durable Maturity coordination and cannot merge. WGCF owns readiness. Prototype
Studio owns canonical source. Security review #1125 owns the accepted
normal-availability boundary. Related decision:
[ADR-027](../../decisions/adr/ADR-027-dedicated-prototype-maturity-identity.md).

## Root Cause

Prototype Maturity readiness and orchestration were independently activated,
but normal use remained blocked because no dedicated provider identity had been
commissioned or composed with both runtime gates in one reversible Platform
operation.

## Source Changes

The Landing-specific identity operator was extracted into one shared Prototype
workflow mechanism with thin Landing and Maturity entrypoints. Maturity now
pins exact Security, WGCF, OOS, and Studio revisions, projects only its own
credential and state paths, enables WGCF readiness before OOS admission, and
reverses that order for suspension and revocation. Landing remains governed by
its existing contract and regression suite. Runtime actions resolve the
runner-owned WGCF session for the same operator and reject an endpoint that
names any other operator namespace.

The first revocation rehearsal exposed that inherited cleanup still treated
`OOS_RUNTIME_PROFILE` as workflow-owned. Platform restored the value before the
runtime became unavailable, removed that deletion from the shared operator,
added a regression assertion, and repeated a clean activation/revocation cycle.
The clean cycle removed only Maturity while preserving the shared profile and
Prototype Landing.

## Artifact And Deployment Evidence

The value-free
[Prototype Maturity normal-availability evidence](../evidence/prototype-maturity-normal-availability-2026-09-11.json)
binds the exact implementation commit, provider installation, repository
ruleset, Vault version, deployment images, runtime/session bindings, lifecycle
receipts, rehearsal correction, and final active state. No private key,
installation token, WGCF caller secret, or authorization header is recorded.

## Live Verification

The dedicated GitHub App is installed only on
`mfshaf7/workspace-prototype-studio` with Metadata read, Contents write, Pull
requests write, and Checks read. The active `main` ruleset requires human pull
request approval and trusted validation, dismisses stale approvals, denies
force-push and deletion, and gives the App no bypass role. The private key is
held at the contracted Vault path, version `2`.

Platform enabled the exact WGCF Maturity readiness gate before projecting and
enabling OOS Maturity. Both Deployments remained ready after explicit pod
replacement, and both health and readiness endpoints returned HTTP 200. The
WGCF runtime image is attested as
`sha256:204ab4254f03b5177b2375b0fbe47a020165ea7db322f655aaa4fd250a4c14d0`.
Repeated delivery issued a distinct token and revoked the prior token.
Suspension disabled OOS before WGCF while retaining projection and state. Clean
revocation removed the Maturity Secret, environment, mounts, and WGCF gate
while preserving Landing and shared OOS profile state. Final delivery restored
the approved active `dev-integration` posture. No stage or production runtime
changed.

## Rollback

Use `suspend` to stop new Maturity work while retaining identity projection and
coordination state. Use `revoke` to revoke the token, remove the OOS projection,
and then remove the WGCF gate. Neither path removes the shared OOS runtime
profile, Prototype Landing, Studio source, canonical Git history, or retained
evidence.

## Follow-Up Actions

ART #1132 owns the normal Console operating proof. This Platform record does
not claim browser-path success or final Prototype Maturity availability until
that independent proof closes.
