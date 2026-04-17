# Governed Runtime Lifecycle Model

## Purpose

This standard defines the shared vocabulary for governed runtime lifecycle
control.

The goal is to give products and selected shared components a deterministic,
auditable way to:

- keep user traffic live
- stop product traffic through the owning deployment boundary without
  necessarily removing every support surface
- suspend the runtime itself
- enter a stronger incident posture when ordinary suspension is not enough

## Shared State Vocabulary

Use these state names when a governed runtime lifecycle exists:

| State | Meaning |
| --- | --- |
| `live` | runtime is active and normal user traffic is allowed |
| `traffic-stopped` | normal product traffic is intentionally blocked through the owning control plane while selected operator or evidence surfaces may remain |
| `suspended` | runtime is removed or otherwise disabled through the owning control plane |
| `quarantined` | incident state with stricter controls than ordinary suspension |

These names are shared vocabulary. They are not a blanket requirement that
every product or shared component must support every state.

## Profile Model

Each governed product or component should publish a lifecycle profile that
declares:

- supported states
- how traffic is cut in each non-live state
- which runtime or support surfaces remain in each state
- whether promotion is allowed in each state
- whether verification becomes inactive in each state
- whether an incident reference is required
- what must happen before returning to `live`

The profile belongs in the owning product or component docs and contracts.

## Shared Control Expectations

### `live`

- runtime active
- normal user traffic active
- verification expected
- promotion allowed

### `traffic-stopped`

- normal user traffic blocked
- traffic cut must happen at a product or deployment boundary, not only as a
  channel-specific application behavior
- selected support surfaces may remain if the owner profile says so
- verification inactive until the lifecycle returns to `live`
- promotion allowed unless the product profile says otherwise
- use when the product should go quiet without tearing down every governed
  support surface

### `suspended`

- runtime not active
- verification inactive
- promotion may still update the desired contract
- use when the runtime should be down entirely

### `quarantined`

- incident state, not just operator convenience
- runtime typically not active unless the product profile explicitly keeps a
  restricted recovery surface
- verification inactive
- incident reference required
- promotion blocked by default unless the product profile explicitly allows an
  override path
- returning to `live` requires stronger review and fresh verification

## Operator And Security Rules

- Lifecycle source of truth must stay in Git under the owning release authority.
- Lifecycle changes must be reviewable, attributable, and reversible.
- Lifecycle state must be visible to operators through the owning runtime or
  platform surface.
- `traffic-stopped` must not silently widen privilege by leaving alternate
  ingress or hidden network paths active.
- `quarantined` must not be resumable casually; it is an incident control, not
  a convenience toggle.
- Promotion and verification rules must be explicit for every non-`live` state.

## OpenClaw Reference Profile

OpenClaw is the reference implementation for this standard.

Its current prod profile is:

| State | Runtime / support surfaces | User traffic | Promotion | Verification |
| --- | --- | --- | --- | --- |
| `live` | active | Telegram active | allowed | `pending` or `recorded` |
| `traffic-stopped` | `openclaw-gateway` removed; `platform-secrets-prod` and `platform-version` retained | none | allowed | `inactive` |
| `suspended` | pruned from prod root | none | allowed | `inactive` |
| `quarantined` | pruned from prod root | none | blocked | `inactive` |

OpenClaw-specific resume expectations:

- returning from `traffic-stopped` to `live` requires fresh prod smoke/UAT
- returning from `suspended` to `live` requires fresh prod smoke/UAT
- returning from `quarantined` to `live` requires explicit incident follow-up
  plus fresh prod smoke/UAT

## Product And Component Guidance

When onboarding a future product or shared component:

1. Decide whether it actually needs a governed runtime lifecycle.
2. If yes, choose the smallest supported state set that matches the real
   operating model.
3. Publish the lifecycle profile in the owner docs and contracts.
4. Keep runtime behavior and operator docs aligned with that profile.

Do not copy the full OpenClaw state set blindly. Reuse the vocabulary, not the
implementation details.
