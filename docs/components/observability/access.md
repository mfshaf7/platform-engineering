# Observability Access

## Grafana

- prod Windows/operator URL for the platform baseline: `http://127.0.0.1:32080`
- prod WSL fallback:

```bash
k3s kubectl -n observability port-forward svc/platform-observability-prod-grafana 3000:80
```

- credential source: `kv/platform/observability/prod/grafana-admin`

## Prometheus

- prod Windows/operator URL for the platform baseline: `http://127.0.0.1:32090`
- prod WSL fallback:

```bash
k3s kubectl -n observability port-forward svc/platform-operator-ui-auth-proxy 9090:9090
```

- credential source: `kv/platform/observability/prod/operator-ui-auth`

## Alertmanager

- prod Windows/operator URL for the platform baseline: `http://127.0.0.1:32093`
- prod WSL fallback:

```bash
k3s kubectl -n observability port-forward svc/platform-operator-ui-auth-proxy 9093:9093
```

- credential source: `kv/platform/observability/prod/operator-ui-auth`

## Stage

Stage observability endpoints are configured in source, but they are only valid
when stage is deliberately resumed.

Use:

- [../../runbooks/access-platform-uis.md](../../runbooks/access-platform-uis.md)
- [../../runbooks/access-grafana.md](../../runbooks/access-grafana.md)
- [grafana.md](grafana.md)
- [prometheus.md](prometheus.md)
- [alertmanager.md](alertmanager.md)
