# ADR-014: Governed Active-Stack Runtime Drill And Restore Workflow

## Status

- Accepted
- The shared drill taxonomy is extended by
  [ADR-018](ADR-018-permit-gated-component-commissioning-proof.md).

## Context

The platform already has stronger governed delivery patterns for some lanes,
especially OpenClaw stage rehearsal and bounded prod lifecycle control.

That was enough for product-specific drills, but it broke down when a broader
runtime exercise was needed:

- OpenClaw became the de facto drill path because it was the only mature
  product-specific workflow
- the operator intent was broader than OpenClaw and actually meant the current
  active operator-critical stack
- there was no explicit distinction between:
  - product-only drill
  - active-stack drill
  - environment-complete drill
  - lifecycle-control drill
  - governed promotion or rehearsal
- there was no platform-owned rule that restore means the exact pre-drill live
  baseline rather than whatever GitHub `main` currently declares

That gap creates real control risk:

- drill scope can be under-declared
- operators can overstate scope when only the active mixed-lane stack was
  tested
- temporary drill activation can drift into untracked live-state change
- later operators cannot tell whether the environment was actually restored

The platform therefore needs a shared runtime-drill model, not another product-
local workaround.

## Decision

Adopt a shared governed runtime-drill model in
[../../standards/governed-runtime-drill-model.md](../../standards/governed-runtime-drill-model.md).

That model makes these decisions explicit:

- runtime drills are a distinct workflow class from governed promotion
- runtime drills use `runtime-drill` authority:
  - captured pre-drill baseline
  - scoped local source or runtime activation path
- the shared runtime drill types established by this decision are:
  - `product-runtime-drill`
  - `active-stack-runtime-drill`
  - `environment-complete-runtime-drill`
  - `lifecycle-control-drill`
- `component-commissioning-proof` is added by ADR-018 for a permit-gated,
  lifecycle-neutral proof of one component and its exact participating workers
- the initial active-stack drill scope for this workspace includes:
  - `OpenClaw`
  - `OpenProject`
  - `operator-orchestration-service`
  - `Vault`
  - `External Secrets`
  - `platform-postgresql`
  - `Observability`
  - `platform-dashboards`
  - required host bridge surfaces
- every runtime drill must capture a pre-drill baseline snapshot before
  activation
- every runtime drill restores to `exact-baseline` by default
- if the operator intentionally keeps the post-drill state instead of
  restoring the baseline, the work is no longer a drill and must be
  reclassified as a governed change

This ADR defines the control model only.

The machine-readable drill profile, operator script, primary runbook, and
security delta review are follow-on implementation work.

## Consequences

### Positive

- the platform now has an explicit control boundary between runtime drill and
  governed promotion
- an active-stack drill can no longer silently collapse into an OpenClaw-only
  path or overstate itself as an estate-complete platform exercise
- restore semantics are now deterministic and reviewable
- future scripts and runbooks can implement one shared model instead of
  embedding local operator assumptions

### Constraints

- runtime drills now require baseline capture before activation
- a drill cannot honestly be called complete without restore proof
- implementation work still has to land:
  - machine-readable drill profile and script
  - primary operator instruction surface
  - security delta review

## Alternatives Considered

- Keep using the strongest product-local workflow and infer broader rehearsal
  intent from operator chat
  - Rejected because it under-specifies scope, overstates what was actually
    tested, and leaves restore behavior ambiguous.
- Treat every broad runtime exercise as governed promotion
  - Rejected because temporary source-backed drill work is not the same thing
    as approving a new desired live state.
- Restore only to the current GitHub `main` posture after a drill
  - Rejected because the operator explicitly needs return-to-baseline behavior,
    and GitHub `main` may not match the exact pre-drill live posture.

## Related Artifacts

- [../../standards/governed-runtime-drill-model.md](../../standards/governed-runtime-drill-model.md)
- [../../standards/governed-runtime-lifecycle-model.md](../../standards/governed-runtime-lifecycle-model.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
