# ADR-015: Platform Observability Baseline And Overlay Model

## Status

- Accepted

## Context

The platform declares observability as a shared component, but the current
implementation still presents it primarily as an OpenClaw-shaped stack.

Current mismatches include:

- the prod Argo application is still named `openclaw-observability`
- key alert and recording-rule names still center on OpenClaw
- the default dashboard is tagged and scoped around OpenClaw-first signals
- drill and readiness language can imply whole-platform coverage when only the
  active operator-critical stack was actually exercised

That mismatch creates three problems:

- operators can confuse product health with platform health
- shared components such as Vault, broker, External Secrets, and PostgreSQL
  appear secondary even though they are part of the platform control surface
- future drill, readiness, and support evidence becomes hard to classify
  honestly because the observability model does not match the architecture it
  is supposed to describe

The user and operator discussion narrowed the target model before
implementation:

- observability should stay a shared platform concern
- OpenClaw should be treated as a product overlay, not the identity of the
  shared stack
- OpenProject should remain a shared-component overlay for now, not a governed
  product overlay
- the migration should be compatibility-phased rather than a hard rename cut
- the model must name its evidence consumers so dashboards, alerts, readiness,
  and drills serve explicit operator decisions

## Decision

Shared observability is defined as a three-layer model:

1. `platform-baseline`
   - owned by `platform-engineering`
   - describes whole-platform control-plane and shared-runtime health
   - includes shared cluster and platform signals such as Argo CD, Vault,
     External Secrets, platform PostgreSQL, shared broker posture, shared
     namespaces, and the observability stack itself
2. `shared-component-overlay`
   - owned by `platform-engineering`
   - provides component-specific telemetry, dashboards, and alerts for shared
     services that sit on top of the baseline
   - current target overlays include:
     - `operator-orchestration-service`
     - `openproject`
     - `vault`
     - `external-secrets`
     - `platform-postgresql`
     - `host-bridge`
3. `product-overlay`
   - owned under the relevant product integration path
   - provides product-specific runtime and user-path monitoring on top of the
     baseline
   - OpenClaw is the first explicit product overlay in this model

Additional rules:

- the platform baseline is the default operator identity of observability
- the default home dashboard must be architecture-wide rather than OpenClaw-first
- all admitted components should expose a minimum telemetry contract:
  - health endpoint
  - metrics endpoint
  - ServiceMonitor or PodMonitor posture
  - stable labels
  - version or release metadata visible in diagnostics
- stable observability labels should distinguish:
  - `layer`
  - `component`
  - `product`
  - `lane`
  - `owner`
- `dev-integration` is optional evidence input, not part of the always-on
  baseline identity
- stage and other suspended lanes may be `inactive`, but that state must be
  explicit in readiness and drill surfaces rather than silently absent
- the shared non-devint broker lane is still part of the declared shared
  component model even when the active delivery lane is devint

The migration stance is compatibility-first:

- define the new model before renaming Argo apps or existing content
- keep current names and live contracts while the baseline and overlay split is
  implemented
- treat naming cleanup and compatibility alias retirement as follow-on work
  after the new model is in force

The machine-readable source for this decision is:

- `docs/components/observability/model.yaml`

## Consequences

What becomes simpler:

- platform health versus product health can be described honestly
- drill and readiness scopes can distinguish active-stack coverage from
  estate-complete coverage
- shared-component evidence has a first-class place instead of being folded
  into OpenClaw
- future product overlays can be added without redefining the shared stack

What becomes harder:

- current OpenClaw-first alerts, recording rules, dashboards, and names now
  need deliberate migration
- compatibility-phase naming will temporarily reflect both old live names and
  new conceptual ownership
- readiness, drill, and support records must be aligned to the new model
  instead of reusing old product-centric language

Required follow-up work and controls:

- implement platform-baseline telemetry, labels, alerts, and default dashboard
- split OpenClaw and shared-component overlays without breaking compatibility
- align readiness, drill, and operator surfaces to the new scope model
- record the security review for the new baseline-versus-overlay boundary
- correct drill scope language so partial coverage is not called full-platform

No change record is required for this ADR by itself because it does not change
live governed state yet. Any live rename, rollout, or environment-state change
that implements this decision should capture a governed change record when it
lands.

## Alternatives Considered

- Keep observability OpenClaw-shaped and let it expand informally
  - Rejected because it preserves the current architecture mismatch and keeps
    shared platform health subordinate to one product
- Treat OpenProject as a product overlay immediately
  - Rejected because OpenProject is still platform-integrated rather than a
    separately governed product rollout train
- Perform a hard rename cut before the model is defined
  - Rejected because it would raise operator friction without first clarifying
    ownership, scope, evidence consumers, and migration semantics
