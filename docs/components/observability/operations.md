# Observability Operations

## Primary Checks

```bash
k3s kubectl -n argocd get application openclaw-observability platform-dashboards-prod
k3s kubectl -n observability get all
```

## Useful Live Checks

```bash
k3s kubectl -n observability get svc openclaw-observability-grafana platform-operator-ui-auth-proxy
k3s kubectl -n observability get pods
```

## Shared Procedures

- [../../runbooks/access-platform-uis.md](../../runbooks/access-platform-uis.md)
- [../../runbooks/access-grafana.md](../../runbooks/access-grafana.md)
- [../../runbooks/bootstrap.md](../../runbooks/bootstrap.md)
