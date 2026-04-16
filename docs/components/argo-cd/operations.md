# Argo CD Operations

## Primary Checks

```bash
k3s kubectl -n argocd get applications
k3s kubectl -n argocd get application platform-root-shared platform-root-prod platform-root-stage
```

## Refresh

```bash
k3s kubectl -n argocd annotate application <app-name> argocd.argoproj.io/refresh=hard --overwrite
```

## Shared Procedures

- [../../runbooks/bootstrap.md](../../runbooks/bootstrap.md)
- [../../runbooks/deploy.md](../../runbooks/deploy.md)
- [../../runbooks/rollback.md](../../runbooks/rollback.md)
