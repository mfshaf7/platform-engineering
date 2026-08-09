# Workspace Governance Control Fabric Release Governance

## Current Release State

WGCF is not approved for platform deployment.

There is currently no approved:

- `stage` Argo application
- `prod` Argo application
- image pin
- platform release record
- runtime support-readiness record
- governed stage or prod operator access path
- approved WGCF validator invocation profile beyond local dev-integration

There is an active local dev-integration access path for API contract and
evidence-custody iteration. That path includes local-k3s PostgreSQL and
profile-scoped MinIO, is local evidence only, and is not a governed stage/prod
deployment.

## Required Gates Before Deployment

The first platform deployment slice must provide:

- approved source revision and image or package provenance
- environment contract for namespace, service account, network policy, and
  secret delivery
- PostgreSQL migration and rollback plan
- identity and authorization model
- security review for runtime, secret, evidence, and AI-adjacent boundaries
- observability and support-readiness checks
- backup and restore expectations for runtime evidence stores
- governed workload identity and method-scoped object-store authorization
- transport and at-rest encryption, retention, deletion, and restore evidence
- validator invocation gates for `devint-shadow`, `stage-readiness`,
  `prod-readiness`, and `break-glass`
- rollback and suspension procedure

The validator invocation gates are defined in
[validator-invocation-gates.md](validator-invocation-gates.md). These gates
must be satisfied before WGCF receipts can replace direct validator evidence
for any normal operator or CI path.

## Release Authority

`platform-engineering` owns whether WGCF is admitted into `dev-integration`,
`stage`, or `prod`.

`workspace-governance-control-fabric` owns implementation readiness only.

`security-architecture` owns security review and acceptance posture.

No local WGCF receipt, ART completion note, or Review Packet may be used as a
substitute for platform release approval.
