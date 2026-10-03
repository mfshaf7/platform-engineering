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
- `runbooks/project-runtime-observations.md`
- `session-projection-policy.yaml`
- `runtime-observation-policy.yaml`
- `cross-domain-activation-policy.yaml`
- `runbooks/activate-cross-domain-awareness.md`
- `runbooks/commission-repository-catalog.md`

## Boundary

- Platform owns the admitted server-side identity/session projection.
- Platform owns the admitted non-secret runtime observation projection.
- `governance-operations-console` owns projection consumption and route
  enforcement.
- `operator-orchestration-service` owns workflow authorization and mutation.
- `security-architecture` owns trust-boundary approval.

The projections contain no credential, token, cookie, or browser authority.
Do not turn this directory into an identity provider or Console backend.

## Current Maturity

The integration is `platform-integrated` for local `dev-integration` only.
It is not a stage or production identity service. Federated human identity and
Security activation remain separate future gates.

Cross-domain activation must use the product-qualified operator command. Do
not launch ad hoc Console processes or inject owner credentials into browser
configuration. Activation may manage only the dedicated Console services and
WGCF history-reader binding; owner state remains outside its rollback boundary.

Repository/Catalog commissioning must use
`make governance-console-repository-catalog`. Generic Console activity is not
evidence for Repository readiness, Catalog mutation, canonical readback, or
denied-path behavior.
