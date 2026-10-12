# Product Lifecycle Maintenance Commissioning

## Summary

Platform commissions the complete Product Publication and Workspace Registry
maintenance sequence approved by Security for Delivery ART work item `#1273`.
The implementation extends the existing `refinement-catalog` composition and
does not introduce another service, database, identity, workflow, control
plane, or ART child.

## Classification

- work home: Workspace Delivery ART `openproject://work_packages/1273`
- Landing Unit: `delivery-894-lifecycle-platform-commissioning`
- owner repo: `platform-engineering`
- runtime lane: local `dev-integration`
- rollout posture: loopback-only, single-operator, synthetic data

## Exact Inputs

- Workspace Governance authority: `fab38a8266512b0004081039b017904c9c55f288`
- WGCF readiness authority: `9d3e5ef1b8fafac1bf0970a7d997021c37052535`
- OOS lifecycle activation: `2bb51556202a9f3819ca99bad3cad06256480db9`
- OOS Security-reviewed ancestor: `786d01c8b1e144f51cc38f6a40d6d986222ac634`
- Console maintenance source: `9c1b9117a98a59662ba570d90bce01bc0b869fb0`
- Security decision revision: `d4486a2d37729db97017c90a6a82e4fcf12f7ce6`
- Security decision digest: `sha256:34968ebef73c3b53aad02d3d4ab60f4bca2a6858748f1079a7d42f43ea6efcb2`
- current architecture packet: `wgcf://artifacts/delivery-art/sha256/d3befa35e702948c6bd3e94ad09e32e9005fe7a7cd70548d97af6010e21d3799`
- Security-reviewed architecture anchor: `wgcf://artifacts/delivery-art/sha256/9615edbd0d60d3066e7e6e861f10844b2d2413658002a717b3e48d5f4bd10f47`

## Ownership

- Workspace Registry owns product retirement and restoration.
- Product Publication owns publication posture.
- The Console repository owns every owner manifest.
- OOS owns journals and terminal receipts.
- WGCF owns readiness and immutable ledger evidence.
- Security owns acceptance.
- Platform owns composition, ordering proof, runtime activation, rollback, and
  final reconciliation.

## Root Cause And Correction

The prior Platform policy commissioned only the internal audience slice. It
therefore contradicted the later approved lifecycle-maintenance path by denying
`unlisted` and `archived`, binding work item `#1264`, and verifying only the
original version-one internal receipt. The correction supersedes that policy
with the exact `#1273` sequence and decision while preserving the former
receipt as the immutable starting baseline.

The first commissioning revision still treated the Console checkout as one
exact immutable commit. That contradicted the required later owner-manifest
commits in the same repository. The corrective amendment now treats the
Security-reviewed Console source as a minimum ancestor, requires current clean
`main`, and records the exact selected head in every Platform receipt.

The first live reconciliation also exposed an upgrade-order contradiction:
the composition rolled the new fail-closed OOS source before Platform projected
the matching Security decision. Activation now primes that exact binding before
cross-domain runtime waits, and the operator procedure activates once before
source rollout and once after reconciliation.

## Source Changes

This Landing Unit updates the existing Platform policy, commissioning script,
evidence profile, product-health activation, tests, owner guidance, and primary
runbook as one rollback boundary. No owner workflow or runtime service is
duplicated.

## Artifact And Deployment Evidence

The source proof binds the durable architecture packet and exact Security,
Workspace Governance, WGCF, OOS, and Console revisions listed above. Live
commissioning receipts remain in operator-private Platform state and contain
only stable references, digests, bounded results, and source revisions.

## Controls And Evidence

The verifier requires the ordered active/internal, active/unlisted,
retired/unlisted, retired/archived, active/archived, active/unlisted, and final
active/internal states. It rereads four Product Publication requests, two
Workspace Registry lifecycle requests, four fresh reviewed owner manifests,
the publication receipt chain, and both lifecycle history events. Schema-v2
manifest evidence must match the exact Registry receipt, history event, prior
event, record version, record digest, and resulting posture.

Commissioning executes real authorization, invalid-target, stale-manifest,
replay, ordering, and process-loss probes. Denials are content-addressed and
must leave the accepted publication unchanged. The product-health projection
is activated only for local `dev-integration`, remains read-only, and grants no
lifecycle, publication, runtime, release, access, or Security authority.

## Rollback

Rollback removes only the Product Publication runtime variables, mounts, and
Console metadata. It preserves owner source, human reviews, Workspace
Inventory history, WGCF ledger entries, OOS journals, publication receipts,
and Platform evidence. Reactivation requires exact-source validation and final
readback; it never direct-edits an owner state.

## Live Verification

`make governance-console-product-publication ACTION=commission` executes the
bounded live sequence verification, negative probes, process-loss proof,
restart, rollback, reactivation, and final readback. `ACTION=verify-operating`
and `ACTION=verify-process-crash` are the post-merge evidence-profile entry
points.

## Follow-Up

No client, public, remote, multi-user, stage, or production posture is implied.
Any expansion requires a new Workspace Governance contract, Security decision,
owner-source activation, and Platform commissioning decision.
