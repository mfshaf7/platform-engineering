# Access OpenProject

## Purpose

This runbook defines the local operator access path for OpenProject.

## Preferred Endpoint

- OpenProject: `http://127.0.0.1:32083`

This follows the repo's existing operator pattern:

- fixed NodePort on the local `k3s` node
- Windows localhost reachability refreshed by `PlatformCoreHostStack`

## Credentials

- username: `admin`
- password source: Vault path `kv/products/openproject/prod/admin`
- the upstream chart keeps the bootstrap login name fixed as `admin`

The application database is internal-only at:

- service: `platform-postgresql.platform-postgresql.svc.cluster.local:5432`

Do not store the password in Git-tracked docs.

## Verification

```bash
curl -I http://127.0.0.1:32083/login
make openproject-access
```

## Fallback

If Windows localhost is not responding but the service is healthy inside the
cluster, use the direct WSL node URL printed by:

```bash
make openproject-access
```

Then refresh the managed Windows bootstrap path:

```bash
make render-windows-bootstrap
powershell.exe -NoProfile -Command "Start-ScheduledTask -TaskName 'PlatformCoreHostStack'"
```
