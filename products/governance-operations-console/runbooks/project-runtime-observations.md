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
workload kinds, exact Workspace Inventory product bindings, the product-health
schemas, and every recovery runbook reference.

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

## Product Health Capability

The same policy and collector define a separate
`portfolio-product-runtime-health/v1` projection. It binds product identity to
the exact Workspace Governance product record, the underlying runtime
observation reference and digest, availability, freshness, issue posture, and
the owning recovery route. Products without an admitted runtime observation
remain explicitly `unknown`; they are never inferred healthy from lifecycle or
publication state.

The capability is source-inactive in this Landing Unit. The following command
must fail with `product runtime health publication is source-inactive` and must
not create output or a receipt:

```bash
make governance-console-runtime ACTION=project-product-health ARGS="\
  --runtime-projection <operator-private-runtime-observations.json> \
  --output <operator-private-product-health.json> \
  --receipt <operator-private-product-health-receipt.json>"
```

After Security `#1271` and Platform commissioning `#1273` activate the exact
source revision, that same command becomes the primary publication path.
`inspect-product-health --projection <path>` is read-only and reports only
bounded counts and references.

## Boundary

- Kubernetes workload readiness is not endpoint or workflow success.
- Capability posture means the backing runtime is ready enough to attempt the
  capability; the canonical owner still decides the operation.
- WSL CPU, memory, disk, network, and uptime remain host telemetry and are not
  part of this projection.
- Security approval remains a separate activation decision.
- Product health never activates, repairs, releases, retires, restores, or
  publishes a product and grants no cross-boundary authority.
