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

## Current Live Footprint

- namespace: none
- Argo application: none
- direct operator UI: none
- deployment status: not approved for `stage` or `prod`

WGCF is currently source-backed and local-first. Runtime deployment remains
blocked until platform release gates and security review explicitly approve a
deployment posture.

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
- Temporal-backed worker orchestration, when worker execution is activated
- OPA/Rego policy evaluation
- MinIO or S3 artifact custody, when full artifact preservation is required
- identity, secrets, network exposure, observability, backup, and rollback

None of those dependencies are approved by this document alone.
