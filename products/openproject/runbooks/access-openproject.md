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

## Accepted-Idea Delivery Dev Integration

The persistent `accepted-idea-delivery` profile has a separate local-only
OpenProject instance:

- Windows browser URL: `http://127.0.0.1:18183/login`
- WSL Kubernetes exposure: NodePort `32183`
- Windows mapping: `127.0.0.1:18183` to the current WSL address on port
  `32183`

The enabled `PlatformCoreHostStack` Scheduled Task refreshes this mapping at
Windows logon. The profile owns the Kubernetes Service declaration; Platform
owns the Windows localhost mapping. To refresh the generated bootstrap and run
the task immediately:

```bash
make openproject-refresh-devint-access
```

Use the shared profile entrypoint to inspect the runtime and print its local
credential:

```bash
make devint-access PROFILE=accepted-idea-delivery
```

This endpoint is local `dev-integration` access only. It is not the
platform-integrated OpenProject endpoint and provides no stage or production
evidence.

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

For the accepted-idea delivery profile, the bounded fallback is:

```bash
k3s kubectl -n devint-accepted-idea-delivery-mfshaf7 \
  port-forward svc/devint-accepted-idea-delivery-openproject 18183:8080
```
