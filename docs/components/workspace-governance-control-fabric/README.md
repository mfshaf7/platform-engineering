# Workspace Governance Control Fabric

## Purpose

`workspace-governance-control-fabric` is the future shared platform runtime for
fast governance graph, validation planning, admission, receipts, and ledger
views.

The implementation source repo is:

- <https://github.com/mfshaf7/workspace-governance-control-fabric>

The platform owns deployment readiness and approved runtime state only. It does
not own WGCF contracts, workspace governance doctrine, or security acceptance.

## Start Here

- [architecture.md](architecture.md)
- [access.md](access.md)
- [operations.md](operations.md)
- [release-governance.md](release-governance.md)
- [validator-invocation-gates.md](validator-invocation-gates.md)

## Current Live Footprint

- dev-integration profile: `governance-control-fabric`
- dev-integration namespace: `devint-governance-control-fabric-<operator>`
- dev-integration storage: local PostgreSQL plus profile-scoped
  MinIO/S3-compatible evidence storage on separate PVCs
- Argo application: none
- direct operator UI: none
- deployment status: not approved for `stage` or `prod`

WGCF currently has implementation source plus active local-k3s dev-integration
API, PostgreSQL, and isolated evidence-storage access. The object store uses an
API-only bucket credential, a separate storage-admin credential, namespace-local
network policy, explicit backup and restore actions, and reference-only local
receipts. It does not expose a public object URL or credentials to OOS or
OpenProject.

The local profile does not claim governed transport encryption or encrypted
local-path storage. Governed stage/prod deployment remains blocked until
Platform identity, secret delivery, transport and at-rest encryption, backup,
restore, retention, deletion, and Security gates explicitly approve that
posture.

## Owner Boundaries

- `workspace-governance` owns authority contracts, schemas, maturity rules, and
  workspace-root guidance.
- `workspace-governance-control-fabric` owns the runtime implementation.
- `platform-engineering` owns deployment state, version pinning, environment
  adoption, and promotion gates.
- `security-architecture` owns trust-boundary review and security acceptance.

## Deployment Readiness Summary

Before WGCF can become a live shared component, the platform must have an
approved runtime shape for:

- PostgreSQL metadata and receipt state
- validator invocation profiles and cutover gates
- bounded, idempotent governance activity contracts for OOS-mediated durable
  workflows, when activity execution is activated
- OPA/Rego policy evaluation
- MinIO or S3 artifact custody with governed encryption and lifecycle controls
  beyond the bounded local profile
- identity, secrets, network exposure, observability, backup, and rollback

None of those dependencies are approved by this document alone.

Temporal is a Platform-owned runtime adapter behind OOS. Its presence never
makes WGCF the aggregate orchestrator.
