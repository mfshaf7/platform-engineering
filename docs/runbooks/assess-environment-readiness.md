# Assess Environment Readiness

## Purpose

This runbook is the shared operator surface for the aggregate governed
environment-readiness check.

Use it to answer:

- is `stage` governed-ready overall right now
- is `prod` governed-ready overall right now
- which exact workload record is still blocking readiness

This is an aggregate release-governance check. It is not a generic health or
Argo-sync summary.

## Inputs

- environment:
  - `stage`
  - `prod`
- action:
  - `status`
  - `validate`

The machine-readable source of truth is:

- [../../environments/stage/environment-readiness.yaml](../../environments/stage/environment-readiness.yaml)
- [../../environments/prod/environment-readiness.yaml](../../environments/prod/environment-readiness.yaml)

## Command Surface

Use the top-level shared operator entrypoint:

```bash
make environment-readiness ACTION=status ENVIRONMENT=stage
make environment-readiness ACTION=validate ENVIRONMENT=stage
make environment-readiness ACTION=status ENVIRONMENT=prod
make environment-readiness ACTION=validate ENVIRONMENT=prod
```

The entrypoint runs:

```bash
python3 scripts/validate_environment_readiness.py <action> <environment>
```

## What It Checks

The aggregate check consumes the exact governed release records for the current
environment.

Current stage inputs:

- OpenClaw stage readiness decision
- `operator-orchestration-service` stage readiness
- OpenProject stage readiness
- supporting-component stage support-readiness for:
  - Vault
  - External Secrets
  - PostgreSQL
  - Observability
  - Dashboards

Current prod inputs:

- OpenClaw prod post-promotion verification
- `operator-orchestration-service` prod verification
- OpenProject prod verification
- supporting-component prod support-readiness for:
  - Vault
  - External Secrets
  - PostgreSQL
  - Observability
  - Dashboards

The check fails closed when a required workload record is:

- missing
- stale against its referenced candidate, verification, or contract object
- present but still `pending`
- present but carrying the wrong status for the lane

Explicit `inactive` only counts when the exact workload contract already says
that inactive is the correct posture for that lane.

## Status Vs Validate

Use `ACTION=status` when you need a non-failing report of the current state.

Use `ACTION=validate` when the environment must prove governed readiness before
you continue a release or readiness-sensitive operator step.

Current behavior:

- `status`
  - always prints the aggregate verdict and every per-workload result
  - exits `0`
- `validate`
  - prints the same report
  - exits non-zero if any required workload is not currently acceptable

## Interpretation

The result is only as strong as the underlying records.

Examples:

- if OpenProject stage readiness is still `pending`, the stage aggregate stays
  not ready even when the runtime is reachable
- if prod OpenClaw is intentionally suspended and the prod verification record
  is explicitly `inactive`, the prod aggregate can still treat that workload as
  current rather than silently stale
- if stage observability remains intentionally suspended, the stage aggregate
  accepts its explicit `inactive` support-readiness record instead of forcing a
  fake `approved` state

## Related Docs

- [../standards/governed-release-control-model.md](../standards/governed-release-control-model.md)
- [../../products/openproject/runbooks/release-governance.md](../../products/openproject/runbooks/release-governance.md)
- [../components/operator-orchestration-service/release-governance.md](../components/operator-orchestration-service/release-governance.md)
- [../components/vault/release-governance.md](../components/vault/release-governance.md)
