# WGCF Dev-Integration Evidence Storage

## Summary

- Date: 2026-08-09
- Short title: WGCF dev-integration evidence storage acceptance
- Environment: dev-integration
- Severity: normal platform enablement

## Classification

- Type: shared component dev-integration admission extension
- User-facing impact: WGCF can prove bounded local Delivery ART evidence
  custody, digest verification, backup, and restore without exposing raw
  object-store access to OOS, OpenProject, or a public endpoint.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos:
  - [workspace-governance-control-fabric PR #41](https://github.com/mfshaf7/workspace-governance-control-fabric/pull/41)
  - [workspace-governance PR #140](https://github.com/mfshaf7/workspace-governance/pull/140)
  - [Security review for ART evidence custody and source provenance](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-08-09-art-evidence-custody-and-source-provenance.md)
- Related ADR: None; this extends the already accepted WGCF local profile and
  does not approve a governed stage or production storage architecture.

## Root Cause

- Immediate failure: the WGCF profile had persistent metadata storage but no
  isolated object-storage path for full Delivery ART evidence bodies.
- Actual root cause: prior runtime acceptance covered PostgreSQL metadata and
  reference-only receipts, while evidence custody remained a future gate.
- Why it escaped earlier controls: the earlier profile intentionally deferred
  object storage until artifact identity, credential isolation, lifecycle
  actions, and Security review were concrete enough to test together.

## Runtime Decision

Platform accepts the following bounded local profile extension:

- one namespace-local MinIO/S3-compatible StatefulSet, Service, and 2Gi PVC
- separate storage-admin and WGCF API credentials
- API authorization limited to bucket metadata plus object read and write;
  object deletion is denied
- ingress limited by NetworkPolicy to the WGCF API and temporary maintenance
  workloads
- content-addressed object verification plus reference-only storage receipts
- operator-scoped backup and exact-confirmation restore and reset actions

Local namespace HTTP and local-path PVC storage do not satisfy governed
transport or at-rest encryption. Stage and production remain denied pending
approved workload identity, secret delivery, encryption, retention, deletion,
backup, restore, and Security gates.

## Source Changes

- Repo: `workspace-governance-control-fabric`
- Commit(s):
  - `feb84880a446a3586df4007588c0bf5501330ada` from PR #41,
    `Add isolated WGCF evidence storage to dev-integration`
- Guardrail added:
  - non-delete API storage policy and direct denial proof
  - root and application credential separation checks
  - namespace-local NetworkPolicy isolation checks
  - content-address-preserving backup and restore verification
  - exact confirmation for restore and destructive reset
  - profile tests that reject credential projection into the rendered manifest

## Artifact And Deployment Evidence

- Build workflow run: None; the change is profile orchestration and does not
  modify the WGCF application image.
- Published image tag:
  `ghcr.io/mfshaf7/workspace-governance-control-fabric:sha-4b27a2a`
- Published digest: unchanged by this profile-only landing unit
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: use the shared dev-integration runner for
  backup, confirmed restore, down/up persistence, or confirmed reset.
- Why it was environment drift instead of source defect: None; this is a new
  bounded local profile capability.
- Recovery command or procedure: back up first with `make devint-backup
  PROFILE=governance-control-fabric`; restore with `make devint-restore
  PROFILE=governance-control-fabric BACKUP_FILE=<path>
  CONFIRM=restore-wgcf-evidence`; destructive reset requires `make
  devint-reset PROFILE=governance-control-fabric
  CONFIRM=reset-wgcf-evidence`.

## Live Verification

- App health: WGCF API health and readiness passed after storage reconciliation.
- Deployed image:
  `ghcr.io/mfshaf7/workspace-governance-control-fabric:sha-4b27a2a`
- Namespace: `devint-governance-control-fabric-mfshaf7`
- Functional verification:
  - the API credential read the seeded evidence object and object deletion was
    denied
  - the API workload did not receive the storage root credential
  - OOS and OpenProject received no object-store credential or direct URL
  - backup and confirmed restore preserved object SHA-256
    `1aceed53c88ab2edf8286148a858fcc9ccb04ceec264bd526c6b4749f39cfd1c`
  - normal down/up preserved the PVC and the same content address
  - reset without `CONFIRM=reset-wgcf-evidence` failed closed
- Residual risk: local HTTP, static profile-scoped Kubernetes Secrets, and
  local-path PVC storage are dev-integration evidence only.

## Follow-Up

- Required follow-up: governed stage or production design must separately
  close workload identity, transport and at-rest encryption, retention,
  deletion, backup, restore, and Security approval gates.
- Optional hardening: replace local profile credentials and storage classes
  only through a reviewed Platform and Security landing unit.
- Owner: `platform-engineering`
