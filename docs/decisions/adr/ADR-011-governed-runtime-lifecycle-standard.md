# ADR-011: Governed Runtime Lifecycle Standard

## Status

- Accepted

## Supersedes

- [ADR-010-governed-openclaw-prod-lifecycle.md](ADR-010-governed-openclaw-prod-lifecycle.md)

## Context

ADR-010 introduced a bounded prod lifecycle for OpenClaw with `live` and
`suspended`.

That solved the immediate red-button gap, but the real operating model needs
more than a binary runtime toggle:

- operators sometimes need to keep the runtime up while stopping user traffic
- incident containment is stronger than ordinary suspension and should not look
  like a casual operator convenience state
- future products and selected shared components need shared vocabulary and
  guidance instead of ad hoc local state names

The platform therefore needs a reusable lifecycle standard, not just another
OpenClaw-only control.

## Decision

Adopt a shared governed runtime lifecycle vocabulary in
`platform-engineering/docs/standards/governed-runtime-lifecycle-model.md`:

- `live`
- `traffic-stopped`
- `suspended`
- `quarantined`

Products and shared components may support only a subset of those states, but
must publish a lifecycle profile when they expose a governed runtime lifecycle.

The lifecycle profile must declare:

- supported states
- traffic behavior
- runtime behavior
- promotion behavior
- verification behavior
- incident reference requirements
- resume requirements

OpenClaw becomes the reference implementation of that standard.

Its current prod profile is:

- `live`
  - runtime active
  - Telegram traffic active
  - promotion allowed
  - prod verification active
- `traffic-stopped`
  - `openclaw-gateway` removed from the prod Argo root
  - `platform-secrets-prod` and `platform-version` remain
  - normal product traffic is cut at the deployment boundary
  - promotion allowed
  - prod verification inactive
- `suspended`
  - OpenClaw prod slice removed from the prod Argo root
  - promotion allowed
  - prod verification inactive
- `quarantined`
  - runtime down like `suspended`
  - incident reference required
  - promotion blocked
  - prod verification inactive

## Consequences

### Positive

- the platform now has reusable lifecycle vocabulary for future products and
  shared components
- OpenClaw can be taken quiet at the deployment boundary without keeping
  traffic-control logic inside the Telegram repo
- incident containment is distinguished from ordinary suspension
- promotion and verification behavior are explicit for every non-`live` state

### Constraints

- `traffic-stopped` still requires a real owner-controlled traffic boundary; it
  must not degrade into docs-only intent
- not every product or shared component should copy the full OpenClaw state set
- `quarantined` remains stricter than ordinary operations and must stay
  reviewable

## Alternatives Considered

- Keep ADR-010 as the only lifecycle decision
  - Rejected because it keeps the lifecycle model too OpenClaw-specific and too
    binary for future products.
- Invent product-local lifecycle names as needed
  - Rejected because it creates governance drift and makes future routing,
    review, and operator guidance inconsistent.

## Related Artifacts

- [../../../docs/standards/governed-runtime-lifecycle-model.md](../../../docs/standards/governed-runtime-lifecycle-model.md)
- [../../../products/openclaw/runbooks/manage-prod-lifecycle.md](../../../products/openclaw/runbooks/manage-prod-lifecycle.md)
- [../../../products/openclaw/runtime-contract.md](../../../products/openclaw/runtime-contract.md)
