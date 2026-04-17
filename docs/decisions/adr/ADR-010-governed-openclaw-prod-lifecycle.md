# ADR-010: Governed OpenClaw Prod Lifecycle

## Status

- Accepted

## Context

OpenClaw already had a governed stage lifecycle, but prod lacked an equivalent
product-scoped emergency stop path.

That left a real operational gap:

- operators could not deliberately stop only OpenClaw prod through a governed
  control
- incident containment risked degrading into ad hoc edits to the prod Argo root
- OpenClaw prod smoke evidence and runtime exposure could drift from reality
  without an explicit lifecycle contract

The platform also needs to support a valid operator sequence where prod is kept
quiet while a fixed prod contract is prepared in Git.

## Decision

Introduce a bounded governed prod lifecycle for OpenClaw under
`platform-engineering`.

The initial lifecycle states are:

- `live`
- `suspended`

The lifecycle source of truth is:

- `environments/prod/openclaw-lifecycle.yaml`

The product-scoped controller is:

- `products/openclaw/scripts/set_prod_environment_state.py`

The prod Argo root reflects that contract by governing only the OpenClaw prod
slice:

- `openclaw-gateway-app.yaml`
- `platform-secrets-app.yaml`
- `platform-version-app.yaml`

Suspending OpenClaw prod must not prune unrelated prod applications such as
OpenProject, shared observability, or shared data-plane services.

Prod verification follows lifecycle state:

- `live`
  - `environments/prod/verification.yaml` must be `pending` or `recorded`
- `suspended`
  - `environments/prod/verification.yaml` must be `inactive`

Promotion may still update the prod contract while prod is suspended. The
lifecycle state, not promotion alone, decides whether the OpenClaw prod runtime
is active.

## Consequences

### Positive

- OpenClaw prod now has a real governed red-button path
- incident containment no longer requires broad manual edits to the prod Argo
  root
- operators can prepare a fixed prod contract while keeping prod OpenClaw down
- the platform has a reusable pattern for future product-level emergency
  lifecycle controls

### Constraints

- this ADR introduces only a bounded initial lifecycle, not a full
  `traffic-stop` or `quarantined` model yet
- shared prod services remain outside this control
- fresh prod smoke or UAT is still required after returning prod to `live`

## Alternatives Considered

- Manual prod Argo edits or broad root-kustomization changes
  - Rejected because they are harder to audit, too easy to over-prune, and do
    not leave a durable product-scoped control surface.
- A richer multi-state incident model immediately (`traffic-stop`,
  `quarantined`, and others)
  - Deferred because the immediate gap is bounded OpenClaw prod suspension, and
    shipping the narrower governed control now is safer than designing a larger
    state machine before it is needed.

## Related Artifacts

- [../../../products/openclaw/runbooks/manage-prod-lifecycle.md](../../../products/openclaw/runbooks/manage-prod-lifecycle.md)
- [../../../products/openclaw/runtime-contract.md](../../../products/openclaw/runtime-contract.md)
- [../../../products/openclaw/visibility-and-operations.md](../../../products/openclaw/visibility-and-operations.md)
- [OpenClaw prod emergency lifecycle review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/products/2026-04-17-openclaw-prod-emergency-lifecycle.md)
