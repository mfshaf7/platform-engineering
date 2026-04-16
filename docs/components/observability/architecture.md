# Observability Architecture

## Role

This is the shared observability stack for the platform.

It currently covers:

- Grafana
- Prometheus
- Alertmanager
- shared dashboards
- the operator auth proxy in front of Prometheus and Alertmanager

## Current Live Shape

- prod namespace: `observability`
- prod Argo applications:
  - `openclaw-observability`
  - `platform-dashboards-prod`
- stage namespace: `observability-stage`
- stage source exists, but stage observability is not currently deployed while
  stage is suspended

## Model

Current implementation shape:

- Grafana is exposed directly on a NodePort
- Prometheus and Alertmanager are exposed through
  `platform-operator-ui-auth-proxy`
- shared dashboards are deployed separately from the base stack
- stage observability is an environment-scoped variant, not a permanently live
  operator surface

## Read With

- [../../architecture/overview.md](../../architecture/overview.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
- [../../standards/observability.md](../../standards/observability.md)
