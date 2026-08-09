# ADR-019: WGCF Dev-Integration Evidence Storage

## Status

- Accepted

## Context

The Workspace Governance Control Fabric (WGCF) needs to retain full Delivery
ART evidence bodies while keeping OpenProject and the Operator Orchestration
Service (OOS) limited to references and workflow state. The existing
dev-integration profile persisted WGCF metadata in PostgreSQL but did not own a
bounded object-storage path for evidence custody.

Using another service's database or passing object-store credentials through
OOS would blur ownership and expose evidence bodies beyond WGCF. Treating a
local storage proof as a governed stage or production design would overstate
the current security posture because transport encryption, workload identity,
managed secret delivery, retention, and governed backup controls are not yet
approved.

## Decision

Extend only the active WGCF `dev-integration` profile with namespace-local,
S3-compatible evidence storage.

The accepted local boundary:

- runs one MinIO StatefulSet, ClusterIP Service, and 2Gi persistent volume in
  the operator-scoped WGCF namespace
- gives the WGCF API a separate application credential with bucket metadata,
  current and explicit-version object read, and object write permissions while
  denying object deletion
- reserves the root credential for the storage workload and exact temporary
  maintenance Jobs
- enables object versioning and requires receipts to bind the accepted object
  version ID plus content digest
- proves with the application identity that a same-key overwrite leaves the
  receipt-bound bytes retrievable, then restores the accepted payload as current
- restricts ingress with a namespace-local NetworkPolicy to the WGCF API and
  maintenance ServiceAccount
- keeps OpenProject and OOS on reference-only contracts with no storage URL or
  credential
- requires digest verification for stored evidence and for backup/restore
  archives before live objects are replaced
- requires exact operator confirmation for restore and destructive reset
- requires storage-affecting owner commands to verify the active workspace
  registry and this Platform acceptance record before changing runtime state
- fails profile activation closed unless the referenced Security review exists
  at the declared `security-architecture` source path and matches its pinned
  content SHA-256

This decision authorizes a bounded local development profile only. It does not
approve this MinIO instance, these static Kubernetes Secrets, local HTTP, or
the local-path storage class for stage or production.

## Consequences

What becomes simpler:

- WGCF owns evidence metadata, object custody, integrity receipts, and recovery
  within one explicit local boundary
- OOS and OpenProject can coordinate evidence without receiving evidence-store
  authority
- local backup, restore, persistence, and credential-isolation behavior can be
  proved before a governed runtime is designed

What becomes stricter:

- profile activation requires concrete Security review evidence
- every deployed image identity and live storage proof must be recorded in the
  associated change record
- restore must validate each archive member, size, and digest before mutation
- evidence acceptance must use the version-qualified storage reference rather
  than resolving only the mutable current object at a reused key
- stage or production remains denied until Platform and Security separately
  approve workload identity, encrypted transport and storage, managed secrets,
  retention and deletion, and governed backup and restore

The applied local proof is recorded in
[WGCF dev-integration evidence storage acceptance](../../records/change-records/2026-08-09-wgcf-devint-evidence-storage.md).

## Alternatives Considered

- Store full evidence bodies in OpenProject.
  - Rejected because OpenProject owns ART work state and references, not
    artifact custody.
- Let OOS own or proxy the object-store credential.
  - Rejected because OOS orchestrates workflows and must not become an evidence
    store or credential authority.
- Reuse PostgreSQL for full evidence bodies.
  - Rejected because it couples large artifact custody to WGCF metadata storage
    and weakens independent lifecycle and integrity controls.
- Approve the local MinIO shape for stage or production now.
  - Rejected because the local profile does not satisfy governed identity,
    encryption, secret-delivery, retention, or recovery requirements.

## Related Artifacts

- [WGCF component architecture](../../components/workspace-governance-control-fabric/architecture.md)
- [WGCF component operations](../../components/workspace-governance-control-fabric/operations.md)
- [dev-integration profile runbook](../../runbooks/dev-integration-profiles.md)
- [Security review for ART evidence custody and source provenance](https://github.com/mfshaf7/security-architecture/blob/2ad9700c86dfd3a762bcfdb2aba17adbc814ce43/docs/reviews/components/2026-08-09-art-evidence-custody-and-source-provenance.md),
  content SHA-256
  `d0a16096a9ac3f26c85dbeca68364a566aeb9817cd56f7e730995db8ae367158`
- [WGCF owner implementation PR #41](https://github.com/mfshaf7/workspace-governance-control-fabric/pull/41)
