# Bootstrap OpenProject

## Purpose

This runbook adds OpenProject Community Edition to the local `k3s` platform as
an Argo-managed internal service.

## Prerequisites

- the existing `k3s` cluster is healthy
- Argo CD is installed and `platform-root-prod` is reconciling
- External Secrets Operator is healthy
- Vault is available for runtime secret delivery
- the Windows localhost bootstrap path is already managed by
  `PlatformCoreHostStack`

## Assumptions

- OpenProject is a supporting service, not a product source repo
- v1 uses the official upstream Helm chart directly
- v1 uses a standalone platform-managed PostgreSQL service and bundled memcached
- v1 uses `local-path` storage on the single-node `k3s` cluster
- v1 access is a fixed NodePort exposed through the existing Windows localhost
  forwarding pattern

## Files Added

- `products/openproject/README.md`
- `products/openproject/runtime-contract.md`
- `products/openproject/dependencies.md`
- `products/openproject/secrets-and-config.md`
- `products/openproject/runbooks/access-openproject.md`
- `products/openproject/runbooks/bootstrap-openproject.md`
- `products/openproject/runbooks/uninstall-openproject.md`
- `environments/prod/platform-postgresql-secrets/*`
- `environments/prod/argocd/platform-postgresql-secrets-app.yaml`
- `environments/prod/argocd/platform-postgresql-app.yaml`
- `environments/prod/openproject-secrets/*`
- `environments/prod/argocd/openproject-secrets-app.yaml`
- `environments/prod/argocd/openproject-app.yaml`
- `products/openproject/scripts/openproject_apply.sh`
- `products/openproject/scripts/openproject_status.sh`
- `products/openproject/scripts/openproject_access.sh`
- `products/openproject/scripts/openproject_sync_admin_password.sh`
- `products/openproject/scripts/openproject_uninstall.sh`

## Bootstrap Sequence

1. Seed the required secrets in Vault:

```bash
export VAULT_TOKEN='...'
./scripts/bootstrap_vault.sh
kubectl -n vault exec vault-0 -- \
  env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
  vault kv put kv/products/openproject/prod/admin password='<openproject-admin-password>'
kubectl -n vault exec vault-0 -- \
  env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
  vault kv put kv/platform/postgresql/prod/service postgres_password='<postgres-admin-password>'
kubectl -n vault exec vault-0 -- \
  env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
  vault kv put kv/platform/postgresql/prod/openproject password='<openproject-db-password>'
```

Use an OpenProject admin password that is at least 10 characters long. Shorter
passwords are rejected by the application and the sync helper will fail fast.

2. Register and reconcile the PostgreSQL and OpenProject Argo applications:

```bash
make openproject-apply
```

`make openproject-apply` also reconciles the `admin` password from the
Vault-backed Kubernetes secret into the live OpenProject database after the web
deployment becomes healthy.

3. Confirm workload readiness:

```bash
make openproject-status
```

4. Refresh the Windows localhost portproxy set so the new NodePort is exposed on
   `127.0.0.1`:

```bash
make render-windows-bootstrap
powershell.exe -NoProfile -Command "Start-ScheduledTask -TaskName 'PlatformCoreHostStack'"
```

The scheduled task should be backed by the Windows-local bootstrap copy under
`%LOCALAPPDATA%\OpenClaw\bootstrap\`.

## Readiness Checks

Verify:

- `kubectl -n argocd get applications platform-postgresql-secrets platform-postgresql openproject-secrets openproject`
- `kubectl -n platform-postgresql get pods`
- `kubectl -n platform-postgresql get pvc`
- `kubectl -n openproject get pods`
- `kubectl -n openproject get pvc`
- `curl -I http://127.0.0.1:32083/login`

## Windows Access

Primary operator URL:

- `http://127.0.0.1:32083`

Helper:

```bash
make openproject-access
```

## First Login Notes

- username: `admin`
- password source: Vault path `kv/products/openproject/prod/admin`
- the upstream chart does not expose an initial admin username override, only
  password, display name, and email
- in this Argo CD plus External Secrets flow, the upstream chart still seeds the
  database with its default bootstrap password, so this repo explicitly runs
  `make openproject-sync-admin-password` as part of `make openproject-apply`
- the chart is configured to require an admin password reset on first login

## What Is Intentionally Deferred In V1

- ingress and TLS
- SSO or OIDC
- object storage for attachments
- a multi-tenant PostgreSQL provisioning workflow for additional products
- dedicated metrics or dashboard integration

## Storage Caveat

The upstream chart defaults the application PVC to `ReadWriteMany`.
That does not fit the likely `local-path` behavior on this single-node `k3s`
cluster, so this repo forces:

- `persistence.accessModes: [ReadWriteOnce]`
- `persistence.storageClassName: local-path`

The chart already uses a `Recreate` deployment strategy, which matches this
single-writer storage model.
