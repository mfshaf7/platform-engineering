# OpenClaw Observability Overlay

This directory owns the OpenClaw-specific observability overlay that sits on
top of the shared platform observability baseline.

It does not own the shared Grafana, Prometheus, or Alertmanager stack. Those
remain shared platform surfaces under
[`docs/components/observability/`](../../../docs/components/observability/README.md).

## Purpose

Use this directory for OpenClaw-specific telemetry, alerts, dashboards, and
monitor definitions that should not remain in the shared platform observability
tree.

## Current Compatibility Phase

The current migration is compatibility-first:

- shared Argo application names such as `openclaw-observability` remain
  unchanged for now
- shared platform UIs remain platform-owned
- the product overlay owns OpenClaw-specific signals and monitor posture on top
  of the shared baseline

## Current Overlay-Owned Assets

- gateway ServiceMonitor source:
  - [../../../charts/openclaw-gateway/templates/servicemonitor.yaml](../../../charts/openclaw-gateway/templates/servicemonitor.yaml)
- overlay asset catalog:
  - [overlay-assets.yaml](overlay-assets.yaml)

## Read With

- [../README.md](../README.md)
- [../runtime-contract.md](../runtime-contract.md)
- [../visibility-and-operations.md](../visibility-and-operations.md)
- [../../../docs/components/observability/README.md](../../../docs/components/observability/README.md)
- [../../../docs/components/observability/model.yaml](../../../docs/components/observability/model.yaml)
