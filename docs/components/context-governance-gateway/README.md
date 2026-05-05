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

- approved runtime: local-k3s `dev-integration` only after the workspace
  profile lifecycle is `active`
- dev-integration profile: platform-accepted for activation, with workspace
  registry lifecycle still the launch authority
- dev-integration namespace: `devint-context-governance-gateway-<operator>`
  after activation
- Argo application: none
- direct operator UI: none
- API inspection path: `make devint-access PROFILE=context-governance-gateway`
  after activation
- metadata store: local dev-integration PostgreSQL only
- artifact store: local dev-integration MinIO and PVC-backed CGG state only
- deployment status: accepted for local dev-integration activation; not
  approved for `stage` or `prod`

Current approved posture is owner-repo implementation plus platform-accepted
local `dev-integration` runtime activation. No platform operator should create
an ad hoc CGG Service, Deployment, database, object store, dashboard, broker
adapter, or model-facing endpoint outside the active profile and release gates.

## Owner Boundaries

- `workspace-governance` owns context admission standards, workspace contracts,
  and dev-integration lifecycle registry truth.
- `context-governance-gateway` owns implementation.
- `platform-engineering` owns approved deployment state, runtime profile
  admission, version pinning, promotion, backup, restore, and runtime gates.
- `security-architecture` owns trust-boundary review and security acceptance.

## Admission Summary

Before service mode can launch from the shared runner, evidence must exist for:

- active dev-integration profile admission or an approved waiver
- platform acceptance of the local-k3s runtime shape
- local-only secret strategy
- raw and redacted artifact custody in the local dev-integration lane
- metadata persistence
- persistent suspend and destructive reset behavior
- read-only smoke on the persistent working lane
- observability and support readiness
- security revalidation of the implemented runtime

The local CLI implementation alone does not satisfy these gates. The active
dev-integration lane is still local evidence only and does not approve a
governed `stage` or `prod` deployment.

## Security References

- [CGG service-mode security requirements](https://github.com/mfshaf7/security-architecture/blob/main/docs/architecture/components/context-governance-gateway/service-mode-security-requirements.md)
- [CGG service-mode security delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-05-05-context-governance-gateway-service-mode-admission-gates.md)
- [AI security and governance standard](https://github.com/mfshaf7/security-architecture/blob/main/docs/standards/ai-security-and-governance.md)
