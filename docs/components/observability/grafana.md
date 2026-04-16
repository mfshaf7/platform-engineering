# Grafana

## Purpose

Grafana is the operator-facing dashboard surface for platform observability.

## Access

- prod Windows/operator URL: `http://127.0.0.1:32080`
- WSL fallback:

```bash
k3s kubectl -n observability port-forward svc/openclaw-observability-grafana 3000:80
```

- credential source: `kv/platform/observability/prod/grafana-admin`

## Typical Operator Use

- view platform dashboards
- confirm version or runtime metadata surfaced in dashboards
- verify whether a runtime problem is visible as telemetry or only as operator
  anecdote

## Evidence To Capture

- dashboard name
- time range
- panel or datasource error if present
