# Observability Architecture

## Role

This is the shared observability stack for the platform.

The target model is a platform baseline with explicit shared-component and
product overlays. The baseline and overlay split is implemented, and the
shared runtime identities now use platform-owned names.

It currently covers:

- Grafana
- Prometheus
- Alertmanager
- shared dashboards
- the operator auth proxy in front of Prometheus and Alertmanager

## Current Live Shape

- prod namespace: `observability`
- prod Argo applications:
  - `platform-observability-prod`
  - `platform-dashboards-prod`
- stage namespace: `observability-stage`
- stage source exists, but stage observability is not currently deployed while
  stage is suspended

## Target Model

### Platform Baseline

The baseline is the default operator identity of observability. It should
describe shared platform and control-plane health rather than one product.

Target baseline scope:

- Argo CD
- Vault
- External Secrets
- platform PostgreSQL
- operator-orchestration-service
- shared namespaces and cluster-runtime posture
- the observability stack itself

### Shared-Component Overlays

Shared-component overlays add component-specific views on top of the baseline
without redefining the platform identity.

Current target shared-component overlays:

- `operator-orchestration-service`
- `openproject`
- `vault`
- `external-secrets`
- `platform-postgresql`
- `host-bridge`

### Product Overlays

Product overlays provide product-specific runtime and user-path monitoring on
top of the baseline.

Current target product overlays:

- `openclaw`

## Lane Semantics

- prod baseline should be active when the platform live surface is active
- stage baseline and overlays may be `inactive`, but that state must be
  explicit rather than silently absent
- dev-integration can contribute evidence, but it is not part of the always-on
  baseline identity
- the shared non-devint broker lane remains part of the declared platform model
  even when the active delivery lane is devint

## Model

Current implementation shape:

- Grafana is exposed directly on a NodePort
- Prometheus and Alertmanager are exposed through
  `platform-operator-ui-auth-proxy`
- shared dashboards are deployed separately from the base stack
- stage observability is an environment-scoped variant, not a permanently live
  operator surface

The machine-readable source for the target model is
[model.yaml](model.yaml), and the architectural decision source is
[ADR-015](../../decisions/adr/ADR-015-platform-observability-baseline-and-overlay-model.md).

## Read With

- [model.yaml](model.yaml)
- [../../decisions/adr/ADR-015-platform-observability-baseline-and-overlay-model.md](../../decisions/adr/ADR-015-platform-observability-baseline-and-overlay-model.md)
- [../../architecture/overview.md](../../architecture/overview.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
- [../../standards/observability.md](../../standards/observability.md)
