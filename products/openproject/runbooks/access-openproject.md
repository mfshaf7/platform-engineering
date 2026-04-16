# Access OpenProject

## Purpose

This runbook defines the local operator access path for OpenProject.

## Preferred Endpoint

- OpenProject: `http://127.0.0.1:32083`

This follows the repo's existing operator pattern:

- fixed NodePort on the local `k3s` node
- Windows localhost reachability refreshed by `PlatformCoreHostStack`

From WSL, do not assume the same Windows localhost port is reachable inside the
shell. If you need a shell-local endpoint, use:

```bash
k3s kubectl -n openproject port-forward svc/openproject 8080:8080
```

Then open:

- `http://127.0.0.1:8080/login`

## Credentials

- username: `admin`
- password source: Vault path `kv/products/openproject/prod/admin`
- the upstream chart keeps the bootstrap login name fixed as `admin`
- OpenProject requires the password stored there to be at least 10 characters
- if login fails after a fresh deploy or after rotating the Vault password, run
  `make openproject-sync-admin-password`

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
cluster, first use the shell-local fallback:

```bash
k3s kubectl -n openproject port-forward svc/openproject 8080:8080
```

Then refresh the managed Windows bootstrap path:

```bash
make render-windows-bootstrap
powershell.exe -NoProfile -Command "Start-ScheduledTask -TaskName 'PlatformCoreHostStack'"
```

If you still want the helper summary, run:

```bash
make openproject-access
```

The managed Windows task should run the Windows-local bootstrap copy under
`%LOCALAPPDATA%\OpenClaw\bootstrap\`.
