# Access Grafana

## Purpose

This runbook defines the workstation access path for the platform Grafana
instances.

## Endpoints

- prod Grafana: `http://127.0.0.1:32080`
- stage Grafana: `http://127.0.0.1:32081`

These NodePort services are exposed by the local `k3s` host.

## Credentials

Current default credentials:

- username: `admin`
- password: `prom-operator`

Rotate the Grafana admin credential if this remains a long-lived environment.

## Expected Dashboards

- default kube-prometheus-stack dashboards
- `Platform Overview`

## Verification

```bash
curl -I http://127.0.0.1:32080/login
curl -I http://127.0.0.1:32081/login
```
