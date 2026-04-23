# Service Monitors

This directory holds ServiceMonitor and PodMonitor resources that are not owned
directly by a workload chart.

Product-owned monitors should not live here.

Current placement rule:

- shared platform monitors that do not belong to one workload chart may stay in
  this directory
- product-specific monitors should live under the owning product path or inside
  the owning workload chart

OpenClaw now uses its chart-owned ServiceMonitor as the product overlay source
of truth:

- [../../charts/openclaw-gateway/templates/servicemonitor.yaml](../../charts/openclaw-gateway/templates/servicemonitor.yaml)
- [../../products/openclaw/observability/README.md](../../products/openclaw/observability/README.md)
