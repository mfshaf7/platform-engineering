# Repository And Catalog Dev-Integration Commissioning

## Summary

- Date: 2026-10-04
- Short title: Commission the reviewed Repository-to-Catalog operating path
- Environment: local `dev-integration`
- Severity: planned activation

## Classification

- Type: product integration and runtime composition
- Recommendation posture: `extend`
- Work home: Workspace Delivery ART `#1231`
- User-facing impact: the Console can turn one active Workspace Inventory
  repository into an Owner Repo Catalog value through OOS-mediated readiness,
  reviewed mutation, and canonical readback.

## Ownership

- Owning repo or layer: `platform-engineering`
- Existing controls extended: `accepted-idea-delivery` refinement-catalog
  composition, Platform Console session projection, and the managed Console
  cross-domain activation command
- Related repos: `governance-operations-console`,
  `operator-orchestration-service`, `workspace-governance-control-fabric`,
  `workspace-governance`, and `security-architecture`
- Related ADR: None; the source and trust boundary were already accepted by
  the ART architecture packet and Security gate.

## Root Cause

- Immediate gap: exact owner sources existed, but no Platform operating proof
  exercised first-use Repository readiness through the Console server,
  Catalog mutation, canonical readback, restart, denial, rollback, and cleanup.
- Actual cause: earlier generic Console activity receipts proved only owner
  read health, and the first real cross-repo request then exposed that OOS sent
  its semantic Inventory digest where WGCF required the exact `repos.yaml`
  source-content digest. The isolated owner tests had not exercised that exact
  producer/consumer handoff.
- Why it escaped earlier controls: capability-specific runtime acceptance was
  correctly retained for Platform item `#1231`, but the evidence profile first
  omitted the live command and the owner suites independently used locally
  consistent digest fixtures. The full composition was the first surface to
  exercise both controls together.

## Source Changes

- Repo: `platform-engineering`
- Landing Unit: `delivery-1203-repository-catalog-platform-recovery-2`
- Preserved predecessor Landing Unit:
  `delivery-1203-repository-catalog-platform`, whose merged source and
  merge-ready Review Packet remain historical inputs, plus unpublished
  `delivery-1203-repository-catalog-platform-recovery`, whose clean local
  commit was transferred through an evidence-free recovery receipt
- Commit(s): recorded by the finalized ART Review Packet
- Guardrails added:
  - exact architecture, Security, OOS, Console, WGCF, and Workspace Governance
    revision policy;
  - product-qualified primary operator command and runbook;
  - server-only session and caller-secret projection;
  - genuine first-use and existing-readiness mutation paths;
  - stale/false receipt, unauthorized session, OOS, WGCF, and Catalog backend
    denial rehearsals;
  - OOS replacement, managed-service restart, rollback, cleanup, and final
    activation checks; and
  - secret-free capability-specific receipts.
  - an explicit `runtime_and_live` / `live-backend` owner evidence-profile
    command that runs the complete bounded commissioning sequence.
  - session projection validation aligned to Platform's canonical uppercase
    `T`/`Z` UTC session identifier format, with the production-format fixture
    covered by unit tests.
  - owner-checked `0700` state, private, and receipt directories so the state
    creator and session-projection consumer enforce one storage contract.
  - the existing Workspace Intake/Inventory identity activation pins refreshed
    to the exact OOS, Console, Workspace Governance, WGCF, and Security
    revisions accepted by the Repository/Catalog delta review.
  - first-use candidates that include active Inventory repositories absent
    from the canonical Owner Repo Catalog, while reserving a different active
    repository for the WGCF-unavailable denial case.
  - explicit selection and rollback of the reviewed repository-readiness
    contract bundle shipped in the exact WGCF image.
  - the exact OOS content-digest repair, Security re-acceptance, and durable
    architecture v11 binding required before runtime recommissioning.

The initial source landing omitted that evidence-profile command even though
the architecture required live-backend proof. OOS correctly refused
post-merge evidence acquisition. The first real request then failed closed on
the digest-definition mismatch before Catalog mutation. This successor retains
the merged and unpublished source history, binds the landed OOS repair and
Security decision, and does not invent manual evidence or a new ART defect.

## Artifact And Deployment Evidence

- Build workflow run: owner-repository CI-equivalent validation in the
  finalized Review Packet
- Published image tag: local source-mounted OOS dev-integration runtime
- Published digest: not applicable to the loopback Console process
- Recorded prod revision: None
- Argo application revision: None
- Architecture packet:
  `wgcf://artifacts/delivery-art/sha256/115056ba9f888c8ee08de78a17bcea5dd8df40c4a3624eeecbdc7b79148deb17`
- Security review:
  `security-architecture@fd3e58aed30664b4986a0bc22072d3200027298a`
- Runtime receipt digests: recorded after the reviewed candidate completes its
  bounded live rehearsal

## Live Verification

- App health: capability-specific Catalog status, not generic process health
- Functional verification: first-use readiness issuance, existing-reference
  revalidation, Catalog mutation/readback, five denied paths, OOS restart,
  rollback, cleanup, and final activation/status
- Credential boundary: browser credentials denied; distinct OOS and WGCF
  caller secrets remain in operator-private server state
- Residual risk: local single-operator `dev-integration` only; shared identity,
  remote access, stage, and production remain outside approval.

## Follow-Up

- Required follow-up: finalize the Review Packet and close ART `#1231` and
  Feature `#1211` only after source merge and authoritative runtime readback.
- Optional hardening: none inside this Landing Unit; broader environment
  maturity requires separate architecture and Security decisions.
- Owner: `platform-engineering`
