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
  source-content digest. After that repair, the same live path proved WGCF
  still accepted only a synthetic schema-v1 authority fixture while canonical
  `repos.yaml` is schema v2. The isolated owner tests had not exercised the
  complete current authority contract across the producer/consumer handoff.
- Why it escaped earlier controls: capability-specific runtime acceptance was
  correctly retained for Platform item `#1231`, but the evidence profile first
  omitted the live command and the owner suites independently used locally
  consistent digest fixtures. The full composition was the first surface to
  exercise both controls together.

## Source Changes

- Repo: `platform-engineering`
- Landing Unit: `delivery-1203-repository-catalog-platform-recovery-4`
- Preserved predecessor Landing Unit:
  `delivery-1203-repository-catalog-platform`, whose merged source and
  merge-ready Review Packet remain historical inputs, plus unpublished
  recovery Landing Units whose clean local source was transferred through
  exact evidence-free OOS recovery receipts
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
  - the exact OOS content-digest repair, WGCF authority-schema-v2 repair,
    Security re-acceptance, and durable architecture v15 binding required
    before runtime recommissioning.

The initial source landing omitted that evidence-profile command even though
the architecture required live-backend proof. OOS correctly refused
post-merge evidence acquisition. The first real requests then failed closed on
the digest-definition and authority-schema mismatches before Catalog mutation.
This successor retains the merged and unpublished source history, binds the
landed OOS and WGCF repairs plus the exact Security decision, and does not
invent manual evidence or a new ART defect.

The first mutation after those repairs exposed an OpenProject 17.2/Ruby 3.4
serialization compatibility gap: the Catalog setting persisted shared Ruby
object references as YAML anchors, while the current safe Setting loader
rejects aliases with `Psych::AliasesNotEnabled`. The Platform control now
detaches state through JSON before every Setting read/write boundary so the
stored YAML remains alias-free. The single already-written alias-bearing row
is normalized in place before commissioning resumes; no Catalog record is
discarded.

The resumed denial rehearsal also proved that `last_projected_at` is
projection metadata, not persisted Catalog state: it advances whenever OOS
rebuilds the projection after dependency recovery. The commissioning
comparison now excludes only that timestamp while continuing to compare the
complete Catalog value and repository-readiness binding. A receipt or business
field change therefore still fails the side-effect check.

The commissioning restart now waits for the live Console activity endpoint
before requesting capability-specific Catalog readback. Starting the systemd
process is not treated as application readiness, so a normal Next.js startup
window can no longer produce a false `URLError` during the lifecycle proof.

Commissioning is also repeatable after a prior partial run. When all candidate
repositories already have bindings, it uses the normal server-side readiness
preparation path to replace a superseded WGCF receipt before editing. A value
created in the current run still exercises strict verification of its
just-issued receipt, and all later denial checks use the refreshed binding.
The Console now scopes mutation idempotency to the stable operator acceptance
at `f7e1db75739e5fbeb8d7a5ad0d9a7858f2289aac`, so an exact retry replays while
a later deliberate acceptance of the same edit remains a distinct operation.

## Artifact And Deployment Evidence

- Build workflow run: owner-repository CI-equivalent validation in the
  finalized Review Packet
- Published image tag: local source-mounted OOS dev-integration runtime
- Published digest: not applicable to the loopback Console process
- Recorded prod revision: None
- Argo application revision: None
- Architecture packet:
  `wgcf://artifacts/delivery-art/sha256/1f17cc327aa7bbb730ab80877421f6d3d4a459b9e66d528c49e8d36bebb031ff`
- Security review:
  `security-architecture@de4816bcae2b4ff9d8dd40285a1164e1ba0a3834`
- Predecessor recovery-3 commissioning receipt retained as historical proof:
  `sha256:f94fd9351b98839ec9bc0df521e37227df48722cda55557636bf0193f616ce8b`;
  its child receipt set binds activation, status, Catalog rehearsal, restart,
  rollback, cleanup, reactivation, and final status.
- Recovery-4 commissioning receipt: captured by the finalized Review Packet
  from the exact merged source and v15 architecture binding.

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
