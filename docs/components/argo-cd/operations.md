# Argo CD Operations

## Primary Checks

```bash
k3s kubectl -n argocd get applications
k3s kubectl -n argocd get application platform-root-shared platform-root-prod platform-root-stage
```

## Common Failure Signals

- root app is `OutOfSync` or `Degraded`
- child apps are missing from the expected environment root
- sync completes but workloads remain unhealthy in the target namespace
- operators are looking at stage docs while stage is intentionally suspended

## First Response

1. determine whether the issue is in `platform-root-shared`,
   `platform-root-prod`, or `platform-root-stage`
2. identify whether the failure is Git state, chart render, secret-delivery, or
   downstream runtime health
3. compare Argo health with namespace workload health before forcing refresh

## Recovery Sequence

1. inspect the root application and affected child application
2. verify the owning repo and environment contract changed as expected
3. refresh the affected application only if the desired Git state is correct
4. if the app remains degraded, move to the owning component or product
   operations doc rather than repeatedly refreshing Argo

## Refresh

```bash
k3s kubectl -n argocd annotate application <app-name> argocd.argoproj.io/refresh=hard --overwrite
```

## Evidence To Capture

Capture after repair or before escalation:

- root application name
- affected child application name
- sync and health state
- namespace and workload state
- Git revision or promotion PR that should explain the desired state

## Shared Procedures

- [../../runbooks/bootstrap.md](../../runbooks/bootstrap.md)
- [../../runbooks/deploy.md](../../runbooks/deploy.md)
- [../../runbooks/rollback.md](../../runbooks/rollback.md)
