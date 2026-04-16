# Access Grafana

## Purpose

This runbook defines the Grafana-specific access and credential model.

Use [access-platform-uis.md](access-platform-uis.md) for the full current
platform access matrix.

## Endpoints

- prod Grafana: `http://127.0.0.1:32080`
- stage Grafana: `http://127.0.0.1:32081` only when stage observability is
  deliberately resumed

The supported human-operator path is Windows localhost through the
`PlatformCoreHostStack` bootstrap path.

For a WSL shell-local fallback, use:

```bash
k3s kubectl -n observability port-forward svc/openclaw-observability-grafana 3000:80
```

If stage observability is resumed, the stage shell-local fallback is:

```bash
k3s kubectl -n observability-stage port-forward svc/openclaw-observability-sta-grafana 3001:80
```

## Credentials

Current managed credentials:

- username: `admin`
- password is sourced from Vault-backed secret delivery

The intended credential source is:

- `kv/platform/observability/prod/grafana-admin`
- `kv/platform/observability/stage/grafana-admin`

Stage credentials are only relevant when the stage observability stack is
actually running.

## Expected Dashboards

- default kube-prometheus-stack dashboards
- `Platform Overview`

## Verification

```bash
curl -I http://127.0.0.1:32080/login
```

Only run the stage login check when stage observability is resumed:

```bash
curl -I http://127.0.0.1:32081/login
```
