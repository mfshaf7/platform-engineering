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
  - `e6cad75a5c735901c23c8de67df9cee45b2d76d3` from PR #41,
    including the storage implementation, review hardening, recovery archive,
    authority gate, controller-bound credential isolation, receipt-rebinding
    recovery, and stable version-bound receipt proof
  - `3c79031ea4849835107744804fc1506497127847` from this Platform PR,
    preserving a no-overwrite source manifest and result receipt for every
    dev-integration action
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
  - explicit authentication-denial proof for both pre-rotation credential pairs
    after the replacement values are active and before a new storage receipt is
    issued
  - content-address-preserving backup and receipt-rebinding restore verification
  - exclusive backup targets and staged publication so an existing recovery
    bundle cannot be truncated or partially replaced
  - exact profile, namespace, bucket, object, identity, Secret, and
    version-qualified reference validation before a receipt enters a backup
  - private regular-file snapshots validated and consumed by restore so later
    edits to the operator-selected archive cannot cross the preflight boundary
  - semantic preflight of every embedded receipt and sidecar binding before any
    object-store mutation, including exact prior version and storage reference
  - canonical object paths and safe receipt names enforced before archive
    extraction or object-store mutation
  - restore-time receipt validation against the active profile, namespace,
    bucket, service identity, and Secret scope before rebinding
  - controller-UID ownership proof for every Pod holding a storage credential;
    labels, names, and ServiceAccounts alone do not authorize a holder
  - provision Job UID and source-owned template verification against the exact
    server-returned Job recorded when provisioning created it
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

- Executed sessions:
  - `governance-control-fabric-mfshaf7-20260809T125535Z`
  - `governance-control-fabric-mfshaf7-20260809T125846Z`
- Combined acceptance proof SHA-256:
  `4801bfa2ac024c50a34182bd32f068db35a7024376e31fe686d1aa0db576a492`
- Every accepted action manifest recorded clean source state at:
  - WGCF: `e6cad75a5c735901c23c8de67df9cee45b2d76d3`
  - Platform runner: `3c79031ea4849835107744804fc1506497127847`
  - workspace authority: `564a63aadbf1214da827503525ba030f38e17e79`
- Action-specific manifest/result SHA-256 pairs:
  - `up`: `a16cc23b5d1338a19ad2609a6a10398b26ce317b1f03610a42ba3d2a1eec62b5` /
    `e9ff976d039ecf0bea209b7899fa11e8cb3fc2e013149a6ac822d6de4c6067b6`
  - `smoke`: `8ca1a94a22f451df54cbe96f3324655c8525cc1676505854d1d47642ee1929f3` /
    `7e5051ce1f78f231c7a9dd2e70635696bb09b81a5c19eed95d4bc0864dba035f`
  - `backup`: `fc8604da14ea7e610244c695186336aa2ea587ef7df7d853001040fb46adb06e` /
    `db4e2d0b066138840170f0ad648c0c8bf49ea02fd1f5f772e5f0c42af5580025`
  - `reset`: `492b8be03d351e16736a7d1b49f67435f3c32e7b581ddb1c068a001be92bd9d2` /
    `9c64f93da1afc629273c1e62505b7bc1bceee8e7585b56a4fda97e7b980d99e1`
  - fresh `up`: `2cd09bc22f2b1950cd407df9708c9ca38b3d835eef8d6466495831d858b1bb73` /
    `c71501879240e77d4ce216dce9e6cf3a9b877e5eb6e335722dda6836d991165c`
  - `restore`: `1a8ea8968bc59bcfc5a77d5d10dbd9c3b1118622c6201df6fd953c4ad47ad459` /
    `f2f42709629277c4b5c2f05b3732924155aa570c23101cbd924da1f979277874`
  - final `smoke`: `2b910da80af487bd276eefad9405ed5a1ce126334678bec576aafc2a61e42e9c` /
    `ceda16e2c3937ece04d73515037f7d16828e7362abc06cf8be6ff7a659cb6027`
- App health: WGCF API health and readiness passed after storage reconciliation.
- Deployed image:
  `ghcr.io/mfshaf7/workspace-governance-control-fabric:sha-4b27a2a`
- Namespace: `devint-governance-control-fabric-mfshaf7`
- Functional verification:
  - the API credential read the seeded evidence object, including an explicit
    accepted version, while object deletion was denied
  - a confirmed reset deleted the operator-scoped namespace and PVCs after
    archiving the backup, then `up` rebuilt the local lane from empty storage
  - restore superseded receipt version
    `d6b8158e-62c6-4206-a1b4-f934d8c8d43e` with newly verified version
    `8841d85d-cec9-4372-b485-4d47d523b9d6`, restored current version
    `86adc33f-783f-4400-8233-91b93f09e9b8`, and retained SHA-256
    `1aceed53c88ab2edf8286148a858fcc9ccb04ceec264bd526c6b4749f39cfd1c`
  - the restore receipt SHA-256 is
    `daf68738ccd43f73dbfce3ec5b2772504267f3f4f44ff80269ea1ebbf642d8cb`
  - the API workload did not receive the storage root credential
  - OOS and OpenProject received no object-store credential or direct URL
  - a labeled maintenance Job and the API evidence read reached storage, while
    an unselected Pod in the same namespace could not establish a connection
  - both root and application credentials were rotated before reconciliation;
    Secret-first rollout completed and the API, provisioner, and storage
    workload all passed afterward
  - explicit signed object reads using both pre-rotation credential pairs were
    rejected after reconciliation, while the replacement credentials passed
  - a later read-only smoke recreated both network probe Jobs and independently
    re-proved the maintenance allow path and unselected-Pod denial
  - backup and confirmed restore after PVC deletion preserved the same object
    SHA-256 and rebound the receipt from its prior version-qualified reference
    to a newly verified immutable version while recording both references in
    the restore receipt
  - the destructive recovery backup SHA-256 is
    `eb1372876d3d328c10d49c29abca1d56fb2e13b9efc9fbce84bf9d1624ce96c1`;
    its embedded storage receipt SHA-256 is
    `193b21592dca064570d0b85b323cb7ce5d163a98f6504d7626f4d9252c2e8c8b`
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
