# Governance Operations Console Platform Integration Notes

This directory owns the Platform side of Governance Operations Console
integration. It does not own Console product source, operator workflow
authority, or Security approval.

## Read First

- `README.md`
- `runtime-contract.md`
- `dependencies.md`
- `visibility-and-operations.md`
- `runbooks/manage-session-projection.md`
- `session-projection-policy.yaml`

## Boundary

- Platform owns the admitted server-side identity/session projection.
- `governance-operations-console` owns projection consumption and route
  enforcement.
- `operator-orchestration-service` owns workflow authorization and mutation.
- `security-architecture` owns trust-boundary approval.

The projection contains no credential, token, cookie, or browser authority.
Do not turn this directory into an identity provider or Console backend.

## Current Maturity

The integration is `platform-integrated` for local `dev-integration` only.
It is not a stage or production identity service. Federated human identity and
Security activation remain separate future gates.
