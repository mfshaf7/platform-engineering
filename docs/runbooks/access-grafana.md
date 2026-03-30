# Access Grafana

## Purpose

This runbook defines the workstation access path for the platform Grafana
instances.

## Endpoints

- prod Grafana: `http://127.0.0.1:32080`
- stage Grafana: `http://127.0.0.1:32081`

These NodePort services are exposed by the local `k3s` host.
Windows localhost forwarding for these ports is managed by the
`PlatformCoreHostStack` bootstrap path.

## Credentials

Current managed credentials:

- username: `admin`
- password is sourced from Vault-backed secret delivery

The intended credential source is:

- `kv/platform/observability/prod/grafana-admin`
- `kv/platform/observability/stage/grafana-admin`

## Expected Dashboards

- default kube-prometheus-stack dashboards
- `Platform Overview`

## Verification

```bash
curl -I http://127.0.0.1:32080/login
curl -I http://127.0.0.1:32081/login
```
