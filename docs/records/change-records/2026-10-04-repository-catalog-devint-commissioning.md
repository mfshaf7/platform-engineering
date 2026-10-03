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
  read health. They could not establish a different Repository/Catalog
  capability.
- Why it escaped earlier controls: capability-specific runtime acceptance was
  correctly retained for Platform item `#1231`; earlier invalid claims came
  from treating generic read evidence as interchangeable with workflow proof.

## Source Changes

- Repo: `platform-engineering`
- Landing Unit: `delivery-1203-repository-catalog-platform`
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

## Artifact And Deployment Evidence

- Build workflow run: owner-repository CI-equivalent validation in the
  finalized Review Packet
- Published image tag: local source-mounted OOS dev-integration runtime
- Published digest: not applicable to the loopback Console process
- Recorded prod revision: None
- Argo application revision: None
- Architecture packet:
  `wgcf://artifacts/delivery-art/sha256/8bdc926a0ec2f591110480edda9516074fd9610906de7b9ca03c03b60b4d7d80`
- Security review:
  `security-architecture@55c6a7e667fa0172fbf6a9943ba3c620108dc74f`
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
