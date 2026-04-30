# Workspace Governance Control Fabric Release Governance

## Current Release State

WGCF is not approved for platform deployment.

There is currently no approved:

- `stage` Argo application
- `prod` Argo application
- image pin
- platform release record
- runtime support-readiness record
- direct operator access path

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
- rollback and suspension procedure

## Release Authority

`platform-engineering` owns whether WGCF is admitted into `dev-integration`,
`stage`, or `prod`.

`workspace-governance-control-fabric` owns implementation readiness only.

`security-architecture` owns security review and acceptance posture.

No local WGCF receipt, ART completion note, or Review Packet may be used as a
substitute for platform release approval.
