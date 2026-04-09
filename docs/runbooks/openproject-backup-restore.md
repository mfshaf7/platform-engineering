# OpenProject Backup And Restore

## Purpose

This runbook covers backup and restore for the v1 OpenProject deployment.

V1 state exists in two places:

- standalone PostgreSQL data in namespace `platform-postgresql`
- the OpenProject shared assets PVC mounted at `/var/openproject/assets`

## Assumptions

- namespace: `openproject`
- PostgreSQL namespace: `platform-postgresql`
- PostgreSQL statefulset: `platform-postgresql`
- web deployment: `openproject-web`
- database name: `openproject`
- database user: `openproject`

Confirm the concrete names before backup:

```bash
kubectl -n platform-postgresql get statefulset,pvc,secret
kubectl -n openproject get deploy,pvc,secret
```

## Backup

### 1. Database dump

```bash
DB_PASSWORD="$(kubectl -n platform-postgresql get secret platform-postgresql-credentials -o jsonpath='{.data.password}' | base64 -d)"
kubectl -n platform-postgresql exec statefulset/platform-postgresql -- \
  env PGPASSWORD="${DB_PASSWORD}" pg_dump -U openproject openproject > openproject.sql
```

### 2. Shared assets archive

```bash
kubectl -n openproject exec deploy/openproject-web -- \
  tar -C /var/openproject/assets -czf - . > openproject-assets.tgz
```

### 3. Secret source

Record the current admin-password source outside Git:

- Vault path `kv/products/openproject/prod/admin`

## Restore

### 1. Stop application writes

```bash
kubectl -n openproject scale deploy/openproject-web deploy/openproject-hocuspocus deploy/openproject-worker-default --replicas=0
```

### 2. Restore the database

```bash
DB_PASSWORD="$(kubectl -n platform-postgresql get secret platform-postgresql-credentials -o jsonpath='{.data.password}' | base64 -d)"
cat openproject.sql | kubectl -n platform-postgresql exec -i statefulset/platform-postgresql -- \
  env PGPASSWORD="${DB_PASSWORD}" psql -U openproject openproject
```

### 3. Restore shared assets

```bash
cat openproject-assets.tgz | kubectl -n openproject exec -i deploy/openproject-web -- \
  tar -C /var/openproject/assets -xzf -
```

### 4. Start workloads again

```bash
make openproject-status
```

If replicas remain scaled down, re-sync the application:

```bash
make openproject-apply
```

## Caveat

This is a straightforward local-platform backup model, not a hardened disaster
recovery design. V1 does not add automated snapshotting, object storage, or PITR.
