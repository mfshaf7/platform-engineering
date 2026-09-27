# Project Console Runtime Observations

## Purpose

Publish one private, short-lived Platform projection of the admitted
`dev-integration` workloads used by the Governance Operations Console. This
surface reports workload readiness and recovery ownership without exposing
credentials or turning Platform into workflow authority.

## Validate

```bash
make governance-console-runtime ACTION=validate
```

Validation checks the policy schema, unique component identities, supported
workload kinds, and every recovery runbook reference.

## Project

Use operator-private paths outside Git:

```bash
make governance-console-runtime ACTION=project ARGS="\
  --output <operator-private-runtime-observations.json> \
  --receipt <operator-private-receipt.json>"
```

The command reads only the exact Kubernetes resources admitted by
`runtime-observation-policy.yaml`. A missing or scaled-down workload projects
`unavailable`; partial readiness projects `degraded`; loss of collector
authority stops publication. Output and receipt files are atomically written
with mode `0600`.

## Inspect

```bash
make governance-console-runtime ACTION=inspect ARGS="\
  --projection <operator-private-runtime-observations.json>"
```

Inspection reports current or stale freshness and aggregate component counts.
The Console must treat observations beyond `validUntil` as stale and must not
convert stale or unavailable state into synthetic success.

## Boundary

- Kubernetes workload readiness is not endpoint or workflow success.
- Capability posture means the backing runtime is ready enough to attempt the
  capability; the canonical owner still decides the operation.
- WSL CPU, memory, disk, network, and uptime remain host telemetry and are not
  part of this projection.
- Security approval remains a separate activation decision.
