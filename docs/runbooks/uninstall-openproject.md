# Uninstall OpenProject

## Purpose

This runbook removes OpenProject from the local platform in a GitOps-safe way.

## Important Rule

Do not delete the live Argo applications first while the Git-tracked manifests
still exist under `environments/prod/argocd/`.

If you do, `platform-root-prod` can recreate them.

## Controlled Removal Sequence

1. Remove these files from Git in a normal repo change:
   - `environments/prod/argocd/platform-postgresql-secrets-app.yaml` only if you also intend to retire the shared PostgreSQL service
   - `environments/prod/argocd/platform-postgresql-app.yaml` only if you also intend to retire the shared PostgreSQL service
   - `environments/prod/argocd/openproject-secrets-app.yaml`
   - `environments/prod/argocd/openproject-app.yaml`
   - the matching entries in `environments/prod/argocd/kustomization.yaml`
   - `environments/prod/platform-postgresql-secrets/` only if the shared PostgreSQL secret-delivery path is no longer needed
   - `environments/prod/openproject-secrets/` if the secret-delivery path is no longer needed
2. Merge that change and let `platform-root-prod` reconcile.
3. Run:

```bash
make openproject-uninstall
```

This removes the Argo applications but leaves namespace data in place.

To remove the shared PostgreSQL applications in the same step:

```bash
REMOVE_POSTGRES=true make openproject-uninstall
```

## Data Purge

To remove application data as well:

```bash
PURGE_DATA=true REMOVE_POSTGRES=true make openproject-uninstall
```

That deletes the `openproject` namespace and, when `REMOVE_POSTGRES=true`, the
`platform-postgresql` namespace and its PVCs.

## State That Remains Unless Removed Explicitly

- Vault path `kv/products/openproject/prod/admin`
- Vault path `kv/platform/postgresql/prod/service`
- Vault path `kv/platform/postgresql/prod/openproject`
- local backup files such as `openproject.sql` and `openproject-assets.tgz`

## Verification

```bash
kubectl -n argocd get application platform-postgresql platform-postgresql-secrets openproject openproject-secrets
kubectl get namespace platform-postgresql
kubectl get namespace openproject
```

## Caution

Namespace deletion is destructive for:

- OpenProject shared assets
- standalone PostgreSQL data when `platform-postgresql` is removed
