# Observability Standard

The target observability model is defined by:

- [../decisions/adr/ADR-015-platform-observability-baseline-and-overlay-model.md](../decisions/adr/ADR-015-platform-observability-baseline-and-overlay-model.md)
- [../components/observability/model.yaml](../components/observability/model.yaml)

## Layer Model

Shared observability is split into:

- `platform-baseline`
- `shared-component-overlay`
- `product-overlay`

The platform baseline is the default operator identity of observability. Shared
component and product overlays add focused views on top of that baseline and do
not redefine the identity of the shared stack.

## Minimum Telemetry Contract

Every admitted managed runtime should expose:

- health endpoint
- metrics endpoint
- deployable ServiceMonitor or PodMonitor posture
- version metadata visible in dashboards or diagnostics

Stable labels should distinguish at least:

- `layer`
- `component`
- `product`
- `lane`
- `owner`

## Decision Consumers

Observability content should support explicit operator decisions rather than
generic monitoring inventory. The current required consumers are:

- operator live diagnosis
- environment verification
- support readiness
- runtime drills
- incident containment and recovery

Dashboard and alert design should name the decision surface they support.

## Lane Semantics

- prod baseline should be active when the platform live surface is active
- stage surfaces may be active or inactive, but that state must be explicit
- dev-integration may supply evidence, but it is not part of the always-on
  baseline identity
- shared lanes that are currently inactive should remain part of the declared
  model rather than disappearing from the architecture

## Current Platform Stack

Prometheus and Grafana remain the default shared platform observability stack.

Platform baseline alerts should cover shared health such as:

- Argo reconciliation drift
- Vault health and readiness
- External Secrets sync failures or degraded secret delivery
- shared broker or control-plane availability
- baseline platform namespace or component health

Product-specific runtime availability should live in the relevant overlay
instead of defining the whole platform baseline.

## Compatibility Rule

The current environment and asset names may stay in place during migration, but
new guidance should not describe the shared stack as OpenClaw-owned. Naming
cleanup follows after the baseline and overlay model is implemented.

## Asset Ownership

Platform-owned assets live under:

- [../../observability/alerts](../../observability/alerts)
- [../../observability/recording-rules](../../observability/recording-rules)
- [../../observability/dashboards](../../observability/dashboards)

Product overlay assets should live under the owning product path once the
overlay split is implemented.
