# Prometheus

## Purpose

Prometheus is the shared metrics and query surface for the platform.

## Access

- prod Windows/operator URL: `http://127.0.0.1:32090`
- WSL fallback:

```bash
k3s kubectl -n observability port-forward svc/platform-operator-ui-auth-proxy 9090:9090
```

- credential source: `kv/platform/observability/prod/operator-ui-auth`

## Typical Operator Use

- query recent runtime metrics
- confirm scrape or rule evaluation health
- verify whether an alert condition should have fired

## Evidence To Capture

- query used
- time window
- whether the issue was missing data, stale data, or bad alert logic
