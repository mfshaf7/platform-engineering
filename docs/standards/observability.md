# Observability Standard

Every managed runtime should expose:

- health endpoint
- metrics endpoint
- deployable ServiceMonitor or PodMonitor
- version metadata visible in dashboards or diagnostics

Prometheus and Grafana are the default platform observability stack.

Platform-owned assets live under:

- [observability/alerts](../../observability/alerts)
- [observability/recording-rules](../../observability/recording-rules)
- [observability/dashboards](../../observability/dashboards)
