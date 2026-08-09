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
  - `89c86fafcbc5a7dd91a722d6b97c56d7c8713ef3` from PR #41,
    including the storage implementation, review hardening, recovery archive,
    authority gate, controller-bound credential isolation, receipt-rebinding
    recovery, and stable version-bound receipt proof
  - `935b6fbf05398d425ddaddf4589ed6911ac97e4a` from this Platform PR,
    preserving a no-overwrite source manifest and result receipt for every
    dev-integration action and dispatching the selected owner worktree rather
    than a different default checkout
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
  - namespace-local pending-rotation custody that survives an interrupted `up`
    and is removed only after both retired credential pairs are denied
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
  - configured seed key, content digest, and bound receipt enforced before
    restore can mutate storage
  - restore-time receipt validation against the active profile, namespace,
    bucket, service identity, and Secret scope before rebinding
  - controller-UID ownership proof for every Pod holding a storage credential;
    labels, names, and ServiceAccounts alone do not authorize a holder
  - provision Job UID and source-owned template verification against the exact
    server-returned Job recorded when provisioning created it
  - exact confirmation for restore and destructive reset
  - owner-side activation gate bound to the active workspace profile and this
    Platform acceptance record at a pinned source commit and content digest
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
  - `governance-control-fabric-mfshaf7-20260809T133906Z`
  - `governance-control-fabric-mfshaf7-20260809T134224Z`
- Retained combined acceptance proof:
  [wgcf-devint-evidence-storage-2026-08-09.json](../evidence/wgcf-devint-evidence-storage-2026-08-09.json)
- Combined acceptance proof SHA-256:
  `c2b43fa0d80a5afe31d3ee14bda62243e7e419fe2868dc54af681eaf7d2eb77d`
- Every accepted action manifest recorded clean source state at:
  - WGCF: `89c86fafcbc5a7dd91a722d6b97c56d7c8713ef3`
  - Platform runner: `935b6fbf05398d425ddaddf4589ed6911ac97e4a`
  - workspace authority: `564a63aadbf1214da827503525ba030f38e17e79`
- Action-specific manifest/result SHA-256 pairs:
  - `up`: `f089e6e0f03eeda221d7005bc99c16e37137e554361d6465cf6c75ad80417a15` /
    `1a02e3cf8b88437c5afed53e3f778caf6c91b71e7501a05915a292c90e8b73c0`
  - `smoke`: `0fb46d7f20f10e6cba244d4f2f630267dea8581b1ff43efd1b1e65640ca7ff9e` /
    `47efde1b49a6578403bae6742e263953b7cfd95718ec65b690603e37e397e656`
  - `backup`: `3af48a1d5efd527a9b1fffe110eddd5495c1abf5ee7f9663114f29f5d3d5089f` /
    `91558be8de4d793445b50d1e80a7d8f9888168bd88205f6d4e96c3c646a38914`
  - `reset`: `af96c1a17dfa4cdecdc83f9c98f3c2604bba0a56aa2b596b86fc75483c277ab4` /
    `87bfa7b0314ebadb31254cdc3e2bc42dff9da2270018e3a03eb35a80dfa92876`
  - fresh `up`: `f33a9c85c9e65352da86b7f6222d65ad05c1f142efb79a63e846a2a7377a22eb` /
    `b186711bcd68ce64225009d2338b534d014fa6dd8407d85605e63c2aac7c55dc`
  - `restore`: `8e134642f849eeaa8baf116670a46731aae323dc7f881fc402a8583c252e07b5` /
    `8fb21718398d71f2d3c55f37ad8da5a3633f3c4e7fdf691f1b0399453c6fe2e3`
  - final `smoke`: `8e65c15218168326ea7e69b750768b7bac2dd86861540b9ad3b0edc0a4d8bc8b` /
    `3bcda00f0e23d73b6adb8a8be6a04389b4df8ea2913edddcc5665a0e7e88aef3`
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
    `8841d85d-cec9-4372-b485-4d47d523b9d6` with newly verified version
    `16c0919a-d325-49e4-886b-1978c35846e8`, restored current version
    `87bca9de-3dbe-4dbd-9cf4-c1be157f0423`, and retained SHA-256
    `1aceed53c88ab2edf8286148a858fcc9ccb04ceec264bd526c6b4749f39cfd1c`
  - the restore receipt SHA-256 is
    `a39d03ba08c1e7948257d6b4b0c4c14532711b9119ae262b6e7d5191b647df74`
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
    `0854fe215822e5f2b5e8949d5037dde51abdaaca2890ead4471e3db94dbe38f0`;
    its backup receipt SHA-256 is
    `f5f90b8875591a3547da5f27b307a03b586e4bd35e855c098f97c17fb6df9906`
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
