# Context Governance Gateway Release Governance

## Current Release State

CGG is approved only for local `dev-integration` operation after workspace
profile activation. It is not approved for governed `stage` or `prod`
deployment.

There is currently approved:

- local-k3s dev-integration runtime shape after workspace activation
- profile-owned API, worker, PostgreSQL, MinIO, and PVC-backed CGG state in the
  local dev-integration namespace
- read-only smoke on the persistent local working lane
- suspend through `devint-down` with PVC and local secret preservation
- destructive local reset through `devint-reset`

There is currently no approved:

- `stage` Argo application
- `prod` Argo application
- image pin or deployed digest
- platform release record with a candidate artifact
- runtime support-readiness record
- governed stage or prod operator access path
- shared stage/prod metadata store
- shared stage/prod raw or redacted artifact store

The inactive gate records are:

- [../../../environments/shared/context-governance-gateway/stage-candidate.yaml](../../../environments/shared/context-governance-gateway/stage-candidate.yaml)
- [../../../environments/shared/context-governance-gateway/stage-readiness.yaml](../../../environments/shared/context-governance-gateway/stage-readiness.yaml)
- [../../../environments/shared/context-governance-gateway/prod-verification.yaml](../../../environments/shared/context-governance-gateway/prod-verification.yaml)
- [../../../environments/shared/context-governance-gateway/artifact-custody-gate.yaml](../../../environments/shared/context-governance-gateway/artifact-custody-gate.yaml)

Those records are gates, not deployment manifests.

## Dev-Integration Activation Gate

The local dev-integration activation gate is satisfied only when all of these
are true:

- build-admitted workspace profile lifecycle for implementation authorization
- active workspace profile lifecycle for self-serve launch
- profile-owned runtime manifest in the owner repo
- platform acceptance of runtime state model, namespace, ports, storage, and
  suspend or reset behavior
- local-only secret strategy
- read-only smoke behavior when state is persistent
- stage handoff checklist
- security review reference for service-mode boundary
- explicit statement that dev-integration is not governed rollout evidence

Platform acceptance covers the local runtime fit and operator surface. It does
not replace the workspace lifecycle flip or security custody review.

## Required Gates Before Stage Candidate

The first governed stage candidate must provide:

- approved source revision and image or package provenance
- environment contract for namespace, ServiceAccount, network policy, secret
  delivery, metadata store, and artifact store
- migration and rollback plan for metadata persistence
- artifact custody and retention gate
- identity and authorization model
- security review for runtime, secrets, raw context custody, AI-adjacent
  boundaries, and downstream adapters
- observability and support-readiness checks
- backup and restore expectations for metadata and artifact stores
- rollback and suspension procedure

## Required Gates Before Production

Production remains blocked until:

- stage candidate is recorded
- stage verification is recorded against the exact candidate
- stage readiness is explicitly approved
- prod environment contract is recorded
- prod post-promotion verification is recorded after live reconciliation
- backup and restore evidence exists for metadata and artifact custody stores
- security acceptance remains current

## Release Authority

`platform-engineering` owns whether CGG is admitted into `dev-integration`,
`stage`, or `prod`.

`context-governance-gateway` owns implementation readiness only.

`workspace-governance` owns workspace contracts and profile lifecycle truth.

`security-architecture` owns security review and acceptance posture.

No local CGG receipt, packet, ART completion note, or Review Packet may be used
as a substitute for platform release approval.
