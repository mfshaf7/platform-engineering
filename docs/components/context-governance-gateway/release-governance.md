# Context Governance Gateway Release Governance

## Current Release State

CGG is not approved for platform deployment.

There is currently no approved:

- active dev-integration launch from the shared runner
- `stage` Argo application
- `prod` Argo application
- image pin or deployed digest
- platform release record with a candidate artifact
- runtime support-readiness record
- governed stage or prod operator access path
- shared metadata store
- shared raw or redacted artifact store

The inactive gate records are:

- [../../../environments/shared/context-governance-gateway/stage-candidate.yaml](../../../environments/shared/context-governance-gateway/stage-candidate.yaml)
- [../../../environments/shared/context-governance-gateway/stage-readiness.yaml](../../../environments/shared/context-governance-gateway/stage-readiness.yaml)
- [../../../environments/shared/context-governance-gateway/prod-verification.yaml](../../../environments/shared/context-governance-gateway/prod-verification.yaml)
- [../../../environments/shared/context-governance-gateway/artifact-custody-gate.yaml](../../../environments/shared/context-governance-gateway/artifact-custody-gate.yaml)

Those records are gates, not deployment manifests.

## Required Gates Before Dev-Integration Activation

The first active dev-integration slice must provide:

- active workspace profile lifecycle for `context-governance-gateway`
- profile-owned runtime manifest in the owner repo
- platform acceptance of runtime state model, namespace, ports, storage, and
  suspend or reset behavior
- local-only secret strategy
- read-only smoke behavior when state is persistent
- stage handoff checklist
- security review reference for service-mode boundary
- explicit statement that dev-integration is not governed rollout evidence

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
