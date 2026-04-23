# Observability

## Purpose

This is the shared observability stack for the platform.

## Start Here

- [model.yaml](model.yaml)
- [architecture.md](architecture.md)
- [access.md](access.md)
- [operations.md](operations.md)
- [release-governance.md](release-governance.md)
- [grafana.md](grafana.md)
- [prometheus.md](prometheus.md)
- [alertmanager.md](alertmanager.md)

## Current Live Footprint

- prod namespace: `observability`
- stage namespace: `observability-stage`

## Platform-Owned Assets

- alerts: [../../../observability/alerts/README.md](../../../observability/alerts/README.md)
- dashboards: [../../../observability/dashboards/README.md](../../../observability/dashboards/README.md)
- recording rules: [../../../observability/recording-rules/README.md](../../../observability/recording-rules/README.md)

## Current Definition Source

- target model and ownership decision:
  - [../../decisions/adr/ADR-015-platform-observability-baseline-and-overlay-model.md](../../decisions/adr/ADR-015-platform-observability-baseline-and-overlay-model.md)
- machine-readable scope model:
  - [model.yaml](model.yaml)
