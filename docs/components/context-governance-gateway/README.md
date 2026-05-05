# Context Governance Gateway

## Purpose

`context-governance-gateway` is the platform-adjacent implementation component
for Operational Context Governance. It captures, normalizes, redacts, slices,
budgets, projects, and audits operational context before that context reaches
AI agents, operators, CI, or automation.

The implementation source repo is:

- <https://github.com/mfshaf7/context-governance-gateway>

The platform owns deployment readiness, runtime profile admission, release
state, storage custody integration, backup, restore, and promotion gates. It
does not own CGG implementation, workspace context-admission contracts,
security acceptance, or governed model invocation.

## Start Here

- [architecture.md](architecture.md)
- [access.md](access.md)
- [operations.md](operations.md)
- [release-governance.md](release-governance.md)
- [artifact-custody-and-retention.md](artifact-custody-and-retention.md)

## Current Live Footprint

- approved runtime: none
- dev-integration profile: proposed only, not self-serve launchable
- dev-integration namespace: none approved
- Argo application: none
- direct operator UI: none
- shared metadata store: none approved
- shared artifact store: none approved
- deployment status: not approved for `stage` or `prod`

Current approved posture is local CLI/source evidence in the owner repo plus
blocked platform admission gates. No platform operator should create an ad hoc
CGG Service, Deployment, database, object store, dashboard, broker adapter, or
model-facing endpoint from this document.

## Owner Boundaries

- `workspace-governance` owns context admission standards, workspace contracts,
  and dev-integration lifecycle registry truth.
- `context-governance-gateway` owns implementation.
- `platform-engineering` owns approved deployment state, runtime profile
  admission, version pinning, promotion, backup, restore, and runtime gates.
- `security-architecture` owns trust-boundary review and security acceptance.

## Admission Summary

Before service mode can start, platform evidence must exist for:

- active dev-integration profile admission or an approved waiver
- service identity and caller authorization
- raw and redacted artifact custody
- metadata persistence
- retention and deletion
- backup and restore
- debug override and break-glass handling
- tamper-evident ledger preservation
- observability and support readiness
- rollback and suspension
- security revalidation of the implemented runtime

None of those gates are satisfied by the local CLI implementation alone.

## Security References

- [CGG service-mode security requirements](https://github.com/mfshaf7/security-architecture/blob/main/docs/architecture/components/context-governance-gateway/service-mode-security-requirements.md)
- [CGG service-mode security delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-05-05-context-governance-gateway-service-mode-admission-gates.md)
- [AI security and governance standard](https://github.com/mfshaf7/security-architecture/blob/main/docs/standards/ai-security-and-governance.md)
