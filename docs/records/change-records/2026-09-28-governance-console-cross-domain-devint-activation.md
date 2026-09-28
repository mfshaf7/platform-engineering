# Governance Console Cross-Domain Dev-Integration Activation

## Summary

- Date: 2026-09-28
- Short title: Activate reviewed OOS and WGCF awareness in the Console
- Environment: local `dev-integration`
- Severity: planned activation

## Classification

- Type: product integration and runtime composition
- User-facing impact: Governance Activity now reads the reviewed OOS and WGCF
  owner projections through the Console server on loopback port `3317`.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `governance-operations-console`,
  `operator-orchestration-service`, `workspace-governance-control-fabric`,
  `workspace-governance`, and `security-architecture`
- Related ADR: None; this activates the already approved product-local
  `dev-integration` boundary.

## Root Cause

- Immediate failure: The merged Console composition had no Platform-owned
  runtime delivery, restart, rollback, or cleanup surface.
- Actual root cause: Source acceptance and operating activation were correctly
  separated, leaving ART `#1201` to compose the exact reviewed revisions.
- Why it escaped earlier controls: It did not escape; Security explicitly held
  operating readiness until Platform produced this proof.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): the `delivery-900-platform-activation` Landing Unit and its
  finalized Review Packet
- Guardrail added:
  - exact-revision activation policy
  - focused unit tests
  - product-qualified operator command
  - activation and rollback runbook

Approved input revisions:

- Console: `a35da32c23af7e2ec530a67d0a04abd70a599cb2`
- OOS: `530e50f12e0e059c33902a551b72f000b82cd82e`
- WGCF: `70eb1f25a56fcda5ed57f3cf79425af8025e8d4f`
- Workspace Governance: `5f2d078ede6f67e18ba165739c748d181bd8b8d6`
- Security approval: `72ad7678099286a4476d5f91b3894f1ca6525029`

## Artifact And Deployment Evidence

- Build workflow run: owner-repository CI-equivalent validation in the Review
  Packet
- Published image tag: OOS and WGCF profile images generated from their exact
  approved source revisions
- Published digest: not applicable to the local Console process
- Recorded prod revision: None
- Argo application revision: None

Secret-free local receipt digests:

- restart: `sha256:3a1ca4438b6d585342c0f427268a93fab524a9f5d162fa08b64bf89255eb0f46`
- rollback: `sha256:7896bd74b15a8bc1b3de94a7b16aa364cdcc4d4dc33bf118b8c5fc07cbd18322`
- cleanup: `sha256:01f9c1d67007120acb5a54a64ad925fa9fb05fb9770347b6e3c739a202cbca43`
- final activation: `sha256:44eb65578236b1c3587a61010676551a7fc94b44451d24d0b77107b0a6930b61`
- fixture-disconnection rehearsal and recovery:
  `sha256:921e79e30c18d2a68af8f8d75b80577ff722628d8d2af7fb7b3a468cfd2eee4f`
- final status with both owners current:
  `sha256:57db00f4c891a00e76a54ab3c656a423fee8526900446d2768911cce111959e0`

## Host Or Runtime Recovery

- Required host/runtime action: retire the stale ad hoc Console process that
  held port `3317`, then make the persistent user service its sole owner
- Why it was environment drift instead of source defect: the process predated
  the managed activation surface and ran the same Console checkout manually
- Recovery command or procedure: follow
  [Activate cross-domain awareness](../../../products/governance-operations-console/runbooks/activate-cross-domain-awareness.md)

## Live Verification

- App health: Console Governance Activity API returned live owner-backed data
- Deployed image: exact OOS and WGCF `dev-integration` revisions listed above
- Pod: OOS and WGCF owner profile workloads were ready
- Functional verification: activation, status, restart, deliberate WGCF
  disconnection without fixture fallback, recovery, rollback, cleanup, final
  activation, and final status all succeeded
- Residual risk: OOS durable orchestration is intentionally inactive, so the
  combined view is partial while OOS lifecycle activity and WGCF history remain
  current. The integration is loopback-only and not stage or production proof.

## Follow-Up

- Required follow-up: finalize the Landing Unit Review Packet and close ART
  `#1201`, Feature `#933`, and Epic `#900` only after source landing and
  authoritative readback
- Optional hardening: stage and multi-user activation remain separate future
  architecture and Security decisions
- Owner: `platform-engineering`
