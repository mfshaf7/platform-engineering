# Alertmanager

## Purpose

Alertmanager is the shared alert routing and silence-management surface for the
platform.

## Access

- prod Windows/operator URL: `http://127.0.0.1:32093`
- WSL fallback:

```bash
k3s kubectl -n observability port-forward svc/platform-operator-ui-auth-proxy 9093:9093
```

- credential source: `kv/platform/observability/prod/operator-ui-auth`

## Typical Operator Use

- inspect current firing alerts
- verify routing and notification grouping behavior
- confirm whether alerts were inhibited, silenced, or never fired

## Evidence To Capture

- alert name
- firing or silence state
- route or receiver behavior
