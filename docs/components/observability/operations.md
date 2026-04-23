# Observability Operations

## Primary Checks

```bash
k3s kubectl -n argocd get application openclaw-observability platform-dashboards-prod
k3s kubectl -n observability get all
```

Compatibility note:

- `openclaw-observability` is still the implementation-time Argo application
  name for the shared platform baseline during migration
- `platform-dashboards-prod` is the shared dashboard overlay on top of that
  baseline

## Common Failure Signals

- Grafana loads but dashboards or datasource-backed panels fail
- Prometheus endpoint is reachable but queries fail or return stale data
- Alertmanager endpoint is reachable but alerts are not routing or not visible
- operator auth proxy is up for one surface and broken for another

## First Response

1. separate the problem into one of these layers:
   - Grafana UI
   - Prometheus data path
   - Alertmanager path
   - auth proxy or exposure path
   - dashboards or alerts content
2. verify whether the issue is prod-only or related to stage being suspended
3. confirm the owning Argo applications are healthy before troubleshooting the
   individual surface

## Useful Live Checks

```bash
k3s kubectl -n observability get svc openclaw-observability-grafana platform-operator-ui-auth-proxy
k3s kubectl -n observability get pods
```

## Recovery Sequence

1. verify the platform baseline Argo app `openclaw-observability` and the
   dashboard overlay app `platform-dashboards-prod`
2. verify service and pod state in `observability`
3. isolate whether the failure is in:
   - dashboards and datasource definitions
   - scrape/rule evaluation
   - auth proxy exposure
   - alert routing
4. use the subcomponent docs below before changing shared observability assets

## Evidence To Capture

Capture:

- affected surface and URL
- Argo app state
- pod and service state
- whether the issue was data, dashboard, auth, or alert routing
- repaired asset or config path if observability content changed

## Subcomponents

- [grafana.md](grafana.md)
- [prometheus.md](prometheus.md)
- [alertmanager.md](alertmanager.md)

## Shared Procedures

- [../../runbooks/access-platform-uis.md](../../runbooks/access-platform-uis.md)
- [../../runbooks/access-grafana.md](../../runbooks/access-grafana.md)
- [../../runbooks/bootstrap.md](../../runbooks/bootstrap.md)
