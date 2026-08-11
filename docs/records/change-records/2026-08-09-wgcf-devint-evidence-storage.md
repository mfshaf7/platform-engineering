# WGCF Dev-Integration Evidence Storage

## Summary

- Date: 2026-08-09
- Short title: WGCF dev-integration evidence storage commissioning acceptance
- Environment: dev-integration
- Severity: normal platform enablement

## Classification

- Type: shared component dev-integration admission extension
- User-facing impact: WGCF has completed bounded local Delivery ART
  evidence-custody commissioning in dev-integration without exposing raw
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

Platform accepts the following bounded local profile extension for controlled
dev-integration activation and post-activation commissioning:

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

The initial acceptance authorized the workspace registry to activate the local
profile so the final commissioning sequence could run; it did not itself count
as final operating evidence. The owner action intentionally rejects an
authority contract that is not on `origin/main`, so exact-head restore and
smoke proof had to wait for the owner, Platform, and registry PRs to land in
dependency order. The required post-activation proof is retained in the
2026-08-11 commissioning addendum below. ART #811 may close only after this
addendum lands and its owner-repository Review Packet is finalized.

## Source Changes

- Repo: `workspace-governance-control-fabric`
- Commit(s):
  - `37db47c960d67542d5d135c72b48817123639593` from PR #41,
    including the storage implementation, review hardening, recovery archive,
    authority gate, controller-bound credential isolation, receipt-rebinding
    recovery, and stable version-bound receipt proof
  - `ab3b7cc5e0a76fb1f9397fd579e6bb3f23e81ffb` from this Platform PR,
    preserving a no-overwrite source manifest and result receipt for every
    dev-integration action, re-executing the runner from the selected Platform
    checkout, and dispatching the selected owner worktree rather than a
    different default checkout
- Uncommissioned hardening validated in source before activation:
  - WGCF `99b3bc3c3488e990268808fe31b56b6b3692cc01`, including transactional
    restore, sealed restore inputs, exact restored-claim whitelisting, and
    direct hashing of the sealed archive descriptor
  - Platform `646b7470b6bc39fc3d7b5c48517e6eec63337339`, including delayed,
    self-contained local action-record publication and best-effort direct
    process-group cleanup. These records remain provisional local context, not
    tamper-resistant evidence or governance authority.
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
  - rebound receipt outputs streamed to private staging files, validated
    against the active scope, and atomically renamed only after complete
    transfer
  - semantic preflight of every embedded receipt and sidecar binding before any
    object-store mutation, including exact prior version and storage reference
  - canonical object paths and safe receipt names enforced before archive
    extraction or object-store mutation
  - configured seed key, content digest, and bound receipt enforced before
    restore can mutate storage, with the primary `storage-receipt` required to
    bind that configured seed directly
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

The retained sessions below are historical operating proof for the bounded
storage design at the explicitly recorded source heads. The later merged-source
commissioning sequence is recorded separately in the 2026-08-11 addendum and
does not retroactively change the source bindings of these earlier sessions.

- Executed sessions:
  - `governance-control-fabric-mfshaf7-20260809T140544Z`
  - `governance-control-fabric-mfshaf7-20260809T140845Z`
  - `governance-control-fabric-mfshaf7-20260809T141235Z` for supplemental
    post-restore credential-retirement proof
  - `governance-control-fabric-mfshaf7-20260809T143731Z` for final
    atomic-receipt restore and read-only smoke proof
- Retained combined acceptance proof:
  [wgcf-devint-evidence-storage-2026-08-09.json](../evidence/wgcf-devint-evidence-storage-2026-08-09.json)
- Combined acceptance proof SHA-256:
  `0ffa9db7e62c3d3155a3ef0e66171873ed4e1e1aa10fee204558e45c40656294`
- The full recovery and credential-rotation sequences retain their own clean
  source bindings at WGCF `d122a0d733ec255bbececb8abdca66a22b023d19`
  and Platform runner `9c8a63c5d7b725986ce52efad99c71d51964a0a2`.
- Final atomic-publication restore and smoke manifests recorded clean source
  state at:
  - WGCF: `37db47c960d67542d5d135c72b48817123639593`
  - Platform runner: `ab3b7cc5e0a76fb1f9397fd579e6bb3f23e81ffb`
  - workspace authority: `564a63aadbf1214da827503525ba030f38e17e79`
- Action-specific manifest/result SHA-256 pairs:
  - `up`: `cea1926c6f390347ed89e8362358808c07cc400017e5c77b028fe2c770c5cdff` /
    `9af33c8d14159b149510986ff57d590a7d8d864188b17570665f1bc9ec15f78a`
  - `smoke`: `60f047f97068c29fb2b4851c735ec99fa4741483f2c0a364646992a69670047e` /
    `0b89e96e5e49875740113211b29c0737adfe31068625474ce9ff0c2b97d48d2b`
  - `backup`: `d7ba3f6a540e140f00d8dc40d76b6753614e81ca864a59e7e238f0f697e66e88` /
    `7b1d0f3752704de859f9fc8386369cc835f1668d0ae97da3a90c8ebf3754db0e`
  - `reset`: `d043297f7a7238fa0b490b89d9dd6ef23445e50ab61dfdc90cef22006fc39bd7` /
    `604c560efcb6ef2fbfc20c7da30c73f824c1b125f84361ae4b53fa22c87df751`
  - fresh `up`: `7757cca33a68148e3bbd9dff289313b443d15eccfab29214c77107ee8bc57d49` /
    `ff4db46e6eba050246856190e4a65c7454616999693897ba972fae5c528a1a45`
  - `restore`: `8be8998b0eea649b1c2b471bb636c3d85b029fa155a60a738be40415ba5a59d4` /
    `d7074bb4b0668928f5f36cb44506c2337549d46a28a0f54da4f383a5d2558b5c`
  - final recovery `smoke`: `77aa73c13f8d219e4d5aa27d461e21c2b69a250c919c4275434bec8280b13e6d` /
    `b6acb76b049184ad5c457d2da4d09478c9f35e0ba2b16933fae05fe240d0e77a`
  - supplemental rotation `up`: `6ffe4bf48a9a5307c6d7d84888420593748f0e3e89293c67ccc5c6a6cd532dc6` /
    `f42550c1dc04a6fc1d25763ff926e8d570b883086d79b86ee5334563447f5afa`
  - final `smoke`: `3b12e2edb883ef283e120e9bc417fc051894a2eb684ad95fd4d5dddecee3dfcf` /
    `3e3670f81eda50213b82c4f266e29973b7ec595b81a3980495bea44019787dea`
  - final-fix `restore`: `3827f1be27e8eccb89dc6ead614ab207149fdb53f1e5089e92c3fcd460f0630f` /
    `242c11e007cb0c437cf1175e9572ac43e6ac25776b44434c89804bda19bfc768`
  - final-fix `smoke`: `2c0421e02180aabd8af8061711151ca65b1e7b938b9b11ac415e1ddda5c6711f` /
    `527687e3dc35a313b7894a00803caa07867d68342c08c7ed658c48b72d19d105`
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
    `0256b561-4aee-4463-86c0-ee1633c4cdca` with newly verified version
    `3b7f99c0-4a4a-4797-98f8-70d7430cbf4b`, restored current version
    `0b676d54-7885-48ae-ab9f-763af7df362d`, and retained SHA-256
    `1aceed53c88ab2edf8286148a858fcc9ccb04ceec264bd526c6b4749f39cfd1c`
  - the restore receipt SHA-256 is
    `92bc2ecdc79fa36c4d64b29329cb87c2e217a759c62d3c2638b012a58aae8411`
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
    `9e1d2e644583442cddc9ab9faadccd57a7e77d69929ab639312b649447ad9b97`;
    its backup receipt SHA-256 is
    `df13d5877422c272dbd5a9a99f6b1f7b03c745470a8cfeb1171758eb6170747c`
  - the retained proof embeds sanitized action bindings and detailed control
    outputs; it contains neither local absolute paths nor credential values
- Residual risk: local HTTP, static profile-scoped Kubernetes Secrets, and
  local-path PVC storage are dev-integration evidence only.

## Post-Activation Commissioning Addendum (2026-08-11)

The required final commissioning sequence ran through the shared Platform
runner after all participating repositories were clean on `main`:

- WGCF: `2844698d069834dd8c6823f50b01f889f50c2704`
- workspace authority: `79efb7f27d77ed5498a28b15bd68a37699e0c5d8`
- Platform runner: `432db3b405e8777ea86975fe2ff70232f246d856`

The single session `governance-control-fabric-mfshaf7-20260811T133008Z`
completed these actions with return code `0`:

- `up` reconciled the active profile and completed storage credential and
  network-isolation proof.
- `backup` retained one evidence object and one receipt binding without
  credentials; archive SHA-256
  `bcfd9aae2a88189ab9ddaccf9bf4ea1f552b457072a26e304b184acae7f7e4a7`.
- confirmed `restore` consumed the sealed content-addressed input, preserved
  content SHA-256
  `1aceed53c88ab2edf8286148a858fcc9ccb04ceec264bd526c6b4749f39cfd1c`,
  and rebound the receipt to a newly server-assigned object version.
- read-only `smoke` passed API health and readiness, authority load, database
  migration, validation-plan dry run, receipt and ledger metadata reads,
  version-bound evidence reads, credential isolation, and live network-policy
  enforcement.

The sanitized retained proof is
[wgcf-devint-evidence-storage-commissioning-2026-08-11.json](../evidence/wgcf-devint-evidence-storage-commissioning-2026-08-11.json),
SHA-256
`156a88aceb9a7f978bac1f661971d5c1d9a2c7aa8668e3f96b76d8cb8e06ece0`.
Raw action artifacts remain operator-local; the Git-tracked proof contains no
credentials or absolute local paths.

This addendum records the operating proof required for ART #811 when read from
merged `main`. It accepts only profile-scoped local dev-integration custody and
does not authorize a governed stage or production evidence store.

## Follow-Up

- Completed commissioning follow-up: confirmed restore and read-only smoke ran
  through the merged shared runner, and the exact source-manifest and result
  digests are retained in the 2026-08-11 evidence addendum.
- Required future follow-up: governed stage or production design must separately
  close workload identity, transport and at-rest encryption, retention,
  deletion, backup, restore, and Security approval gates.
- Optional hardening: replace local profile credentials and storage classes
  only through a reviewed Platform and Security landing unit.
- Owner: `platform-engineering`
