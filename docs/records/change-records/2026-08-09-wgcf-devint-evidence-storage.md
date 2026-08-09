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
    carries the registry binding in
    `contracts/developer-integration-profiles.yaml`, pinned for this acceptance
    at content SHA-256
    `c23f42c3040d4376af46bcec2ff53d3e6810540ab34e4b97ae00dab78a427da6`
  - [Security review for ART evidence custody and source provenance](https://github.com/mfshaf7/security-architecture/blob/2ad9700c86dfd3a762bcfdb2aba17adbc814ce43/docs/reviews/components/2026-08-09-art-evidence-custody-and-source-provenance.md),
    pinned at content SHA-256
    `d0a16096a9ac3f26c85dbeca68364a566aeb9817cd56f7e730995db8ae367158`
- Related ADR:
  [ADR-019: WGCF Dev-Integration Evidence Storage](../../decisions/adr/ADR-019-wgcf-dev-integration-evidence-storage.md)

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
- API authorization limited to bucket metadata plus current and explicit-version
  object reads and object writes; object deletion is denied
- ingress limited by NetworkPolicy to the WGCF API and temporary maintenance
  workloads
- version-bound object verification plus reference-only storage receipts that
  identify the accepted object version and content digest
- operator-scoped backup and exact-confirmation restore and reset actions
- receipt-aware recovery that carries exact accepted bytes, rebinds receipts to
  new server-assigned versions after restore, and records superseded references

Local namespace HTTP and local-path PVC storage do not satisfy governed
transport or at-rest encryption. Stage and production remain denied pending
approved workload identity, secret delivery, encryption, retention, deletion,
backup, restore, and Security gates.

## Source Changes

- Repo: `workspace-governance-control-fabric`
- Commit(s):
  - `a97bb84a9afab7e1cee1cffe59e60ff2749f7cdd` from PR #41,
    including the storage implementation, review hardening, recovery archive,
    authority gate, controller-bound credential isolation, receipt-rebinding
    recovery, and stable version-bound receipt proof
- Guardrail added:
  - non-delete API storage policy and direct denial proof
  - same-key overwrite proof that retrieves the accepted bytes by version ID
    before restoring them as current
  - root and application credential separation checks
  - namespace-local NetworkPolicy isolation checks
  - live maintenance and API allow-path checks plus an unselected-Pod denial
    check against the storage Service, re-executed by every smoke run
  - Secret-first credential rotation before workload digest rollouts
  - immutable root-user and application access-key identities, with rotation
    limited to secret values so prior users cannot remain authorized
  - content-address-preserving backup and receipt-rebinding restore verification
  - exclusive backup targets and staged publication so an existing recovery
    bundle cannot be truncated or partially replaced
  - exact profile, namespace, bucket, object, identity, Secret, and
    version-qualified reference validation before a receipt enters a backup
  - private regular-file snapshots validated and consumed by restore so later
    edits to the operator-selected archive cannot cross the preflight boundary
  - controller-UID ownership proof for every Pod holding a storage credential;
    labels, names, and ServiceAccounts alone do not authorize a holder
  - exact confirmation for restore and destructive reset
  - owner-side activation gate bound to the active workspace profile and this
    Platform acceptance record
  - profile tests that reject credential projection into the rendered manifest

## Artifact And Deployment Evidence

- Build workflow run: None; the change is profile orchestration and does not
  modify the WGCF application image.
- Deployed immutable runtime identities:
  - WGCF API and migration:
    `ghcr.io/mfshaf7/workspace-governance-control-fabric@sha256:fa84422fd16b09c06352478bab1d0eae2a95857dccb2a9be3882337a8f703589`
  - MinIO object storage:
    `docker.io/minio/minio@sha256:a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e`
  - MinIO maintenance client:
    `docker.io/minio/mc@sha256:aead63c77f9db9107f1696fb08ecb0faeda23729cde94b0f663edf4fe09728e3`
  - PostgreSQL metadata storage:
    `docker.io/library/postgres@sha256:4e6e670bb069649261c9c18031f0aded7bb249a5b6664ddec29c013a89310d50`
- Published application tag:
  `ghcr.io/mfshaf7/workspace-governance-control-fabric:sha-4b27a2a`
- Image provenance note: this profile-only landing unit does not build a new
  WGCF image; the identities above were read from the verified live Pod status.
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
  - the API credential read the seeded evidence object, including an explicit
    accepted version, while object deletion was denied
  - a same-key overwrite created version
    `16bb7c15-c95a-4fc9-9edf-5142e920afe8`; accepted version
    `258ab349-5d89-4ea7-b668-8c3f631302e7` remained retrievable with SHA-256
    `1aceed53c88ab2edf8286148a858fcc9ccb04ceec264bd526c6b4749f39cfd1c`
  - the accepted payload was restored as current version
    `d31a3a04-eeda-4e47-9279-c983dbd9d5ac`
  - a confirmed reset deleted the operator-scoped namespace and PVCs after
    archiving the backup, then `up` rebuilt the local lane from empty storage
  - restore superseded receipt version
    `eabbc8e5-ec66-4b4d-83f8-9e25d11784e6` with newly verified version
    `d6b8158e-62c6-4206-a1b4-f934d8c8d43e`, restored current version
    `744d02cd-b844-4952-9b30-f582b84cc174`, and retained SHA-256
    `1aceed53c88ab2edf8286148a858fcc9ccb04ceec264bd526c6b4749f39cfd1c`
  - the active storage receipt now pins
    `wgcf-storage://governance-control-fabric/wgcf-delivery-art-evidence/profile-proof/evidence-custody-v1.json?versionId=d6b8158e-62c6-4206-a1b4-f934d8c8d43e`;
    the restore receipt preserves both old and new references instead of
    claiming a server-assigned version ID survived PVC replacement
  - the API workload did not receive the storage root credential
  - OOS and OpenProject received no object-store credential or direct URL
  - a labeled maintenance Job and the API evidence read reached storage, while
    an unselected Pod in the same namespace could not establish a connection
  - both root and application credentials were rotated before reconciliation;
    Secret-first rollout completed and the API, provisioner, and storage
    workload all passed afterward
  - a later read-only smoke recreated both network probe Jobs and independently
    re-proved the maintenance allow path and unselected-Pod denial
  - backup and confirmed restore after PVC deletion preserved the same object
    SHA-256 and rebound the receipt from its prior version-qualified reference
    to a newly verified immutable version while recording both references in
    the restore receipt
  - a completed backup with SHA-256
    `3f845c42c5e6652516a3cdc76dbd9ba9a45863338f63360c35ede3e1d8cbd708`
    rejected a second write to the same archive or manifest path without
    changing the original bytes
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
