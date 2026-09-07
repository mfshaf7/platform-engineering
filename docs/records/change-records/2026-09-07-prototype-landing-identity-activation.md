---
security_evidence:
  review_areas:
    - identity
    - secrets
    - delivery
  findings: []
  risks: []
  workstreams:
    - WS-007
---

# Prototype Landing Identity Activation

## Summary

- Date: 2026-09-07
- Short title: Activate the bounded Prototype Landing identity projection
- Environment: `dev-integration`
- Severity: Planned capability activation, not an incident

## Classification

ART #1090 under #919/#892; source Landing Unit
`delivery-892-prototype-landing-identity`. This record covers the Platform
identity, runtime projection, rotation, and rollback boundary. Console wiring
is #1091 and composed workflow conformance is #1092.

## Ownership

Platform owns private-key custody, short-lived token issuance, WGCF caller
secret delivery, read-only source and persistent state mounts, rotation, and
revocation. OOS consumes those bindings for Prototype Landing. Prototype Studio
owns canonical source, WGCF owns readiness, and Security review #1089 owns the
trust-boundary decision.

Related decision:
[ADR-026](../../decisions/adr/ADR-026-dedicated-prototype-landing-identity.md).

## Root Cause

Prototype Landing had reviewed source, readiness, and orchestration controls but
no dedicated credential path into Prototype Studio. Reusing another App would
grant authority for the wrong repository or operation. The missing identity was
an intentional activation gate, not a runtime incident.

## Source Changes

Added the exact-repository identity definition and schema, the primary Platform
operator command, bounded Kubernetes projection and teardown, provider and
runtime tests, and this operating record. The command validates App,
installation, owner, repository, permission, event, source revision, caller,
session, credential, and runtime bindings before writing a value-free receipt.

## Artifact And Deployment Evidence

Source validation and sandbox-runtime evidence are recorded by the #1090 Review
Packet. Live App, ruleset, Vault, token projection, rotation, and revocation
evidence will be added here after commissioning. No credential value belongs in
this record.

## Runtime Boundary

Identity projection does not activate Prototype Landing. The deployment patch
forces `OOS_PROTOTYPE_LANDING_ENABLED=false`, while both OOS and WGCF retain
their source-owned activation gates. #1092 must prove the composed workflow
before normal operator availability can be claimed.

## Live Verification

Source validation and sandbox-runtime tests are complete. Live provider App,
ruleset, Vault, Kubernetes projection, rotation, and revocation evidence remains
pending commissioning and will be recorded here before #1090 closes. Prototype
Landing workflow availability is not claimed.

## Rollback

Revoke the issued token, remove the exact OOS Secret and runtime bindings, and
retain source, review, coordination, and receipt history. Do not delete a
Prototype, repository, or canonical Git history as compensation.

## Follow-Up Actions

Commission and exercise the exact App and repository ruleset, then record the
value-free proof in this record and the #1090 Review Packet. #1091 owns Console
wiring. #1092 owns composed runtime activation and conformance after both are
complete.
