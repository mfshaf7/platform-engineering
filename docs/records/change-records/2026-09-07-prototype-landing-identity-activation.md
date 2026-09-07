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

Source validation and sandbox-runtime evidence are recorded by Platform PR
[#235](https://github.com/mfshaf7/platform-engineering/pull/235) and the #1090
Review Packet. Live commissioning is recorded in
[the value-free activation evidence](../evidence/prototype-landing-identity-activation-2026-09-07.json):

- GitHub App id `4861143`, installation id `159774010`
- exact repository `mfshaf7/workspace-prototype-studio` (`1231020532`)
- active human-only merge ruleset `22447647`
- private-key custody at the contracted Platform Vault path, version `2`
- active OOS session `accepted-idea-delivery-mfshaf7-20260907T085034Z`
- credential binding `sha256:341ea9822df4edf33783adddd7ce684b0c6bd2ba9dcf22f2e38eb1624307d3e0`
- runtime binding `sha256:0482c655912be2d27d1d4130ac15668b4e75ab694acbb09448b2a0ecacb06553`

No private key, installation token, or WGCF caller secret is stored in source,
this record, the evidence artifact, or a receipt.

## Runtime Boundary

Identity projection does not activate Prototype Landing. The deployment patch
forces `OOS_PROTOTYPE_LANDING_ENABLED=false`, while both OOS and WGCF retain
their source-owned activation gates. #1092 must prove the composed workflow
before normal operator availability can be claimed.

## Live Verification

Provider readback confirmed the exact account, selected repository, immutable
repository id, permissions, and empty event subscription. Disposable proof PR
[#8](https://github.com/mfshaf7/workspace-prototype-studio/pull/8) proved that
the App can prepare a review branch while direct `main` update, merge,
repository-administration write, and unrelated-repository write all return
`403`. Prototype Studio `main` remained unchanged; the proof PR was closed and
its branch was removed.

The first short-lived token was projected into the active OOS session. Runtime
readback confirmed one ready replica, read-only credential and source mounts,
persistent coordination state, and no client-side Secret payload annotation.
The first rollback revoked the token before Kubernetes exposed that the
teardown patch lacked the `volumeMounts` merge key. Commit `5a80767` corrected
the patch and added regression coverage; retry completed exact runtime cleanup
and retained coordination state. A distinct replacement token was then issued
and projected successfully.

`OOS_PROTOTYPE_LANDING_ENABLED` remains explicitly `false`. This proves the
identity boundary only; Prototype Landing workflow availability is not claimed.

## Rollback

Revoke the issued token, remove the exact OOS Secret and runtime bindings, and
retain source, review, coordination, and receipt history. Do not delete a
Prototype, repository, or canonical Git history as compensation.

## Follow-Up Actions

#1091 owns Console wiring. #1092 owns source-gate activation and composed
runtime conformance after both are complete. Neither child may treat this
identity projection as workflow activation.
