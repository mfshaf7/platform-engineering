# Temporal Dev-Integration Profile

This is the build-admitted persistent local-k3s profile for the platform-owned
Temporal runtime behind `operator-orchestration-service` (OOS).

The runtime source, artifact lock, identity and queue boundary, persistence
shape, and operator commands are implemented. Build admission authorizes that
source work only. The profile cannot launch a runtime until fresh Platform,
Security, and workspace lifecycle gates make it `active`.

## Runtime Boundary

The target local profile contains:

- Temporal server
- Temporal diagnostic UI
- PostgreSQL persistence
- operator-scoped namespace and state

OOS owns workflow clients, workers, definitions, run control, aggregate
projection, and final receipts. Governance Operations Console never calls
Temporal directly.

## Persistence Boundary

- normal `down` preserves PostgreSQL and workflow history
- normal `up` resumes or reconciles the same state
- `reset` is explicitly destructive and operator-scoped
- shared `smoke` remains read-only
- workflow histories carry references and bounded decisions, not secrets, raw
  context, unbounded logs, or duplicated business records

## Source Contracts

- immutable artifacts: `runtime/artifact-lock.yaml`
- identities, task queues, payloads, retention, and observability:
  `runtime/boundary-contract.yaml`
- generated runtime inputs:
  - `runtime/postgresql.yaml.tpl`
  - `runtime/network-boundaries.yaml.tpl`
  - `runtime/temporal-values.yaml.tpl`

No secret value is committed. The active runtime path generates separate
operator-local PostgreSQL admin and Temporal application credentials. Temporal
pods receive only the application secret keys; database backups exclude global
role state and role passwords.

## Current Operator Actions

Build-admitted status and source validation are allowed:

```bash
make devint-status PROFILE=temporal
bash dev-integration/profiles/temporal/scripts/validate_chart.sh
```

Runtime actions remain denied:

```bash
make devint-up PROFILE=temporal
make devint-access PROFILE=temporal
make devint-smoke PROFILE=temporal
make devint-backup PROFILE=temporal
make devint-restore PROFILE=temporal BACKUP_FILE=<path> CONFIRM=restore-temporal
make devint-down PROFILE=temporal
make devint-reset PROFILE=temporal CONFIRM=reset-temporal
make devint-promote-check PROFILE=temporal
```

Once separately activated:

- `devint-down` suspends deployments and PostgreSQL while preserving the PVC
- `devint-backup` quiesces Temporal, writes a mode-0600 operator-local SQL
  backup and digest manifest, then returns to the prior runtime state
- `devint-restore` takes a pre-restore backup, requires
  `CONFIRM=restore-temporal`, and returns to the prior state only after success
- `devint-reset` takes a pre-reset backup, archives evidence outside the
  deleted state root, and requires `CONFIRM=reset-temporal`

## Initial Proof

The first controlled workflow is `validation-readiness-run`. Its OOS workflow
queue is derived as
`oos.validation-readiness-run.v1.<activation-manifest-digest-hex>` so a
revoked generation cannot be polled after reactivation. A restart under the
same still-active manifest reuses its queue; reactivation requires a newly
issued manifest and digest. The workflow must prove
durability across worker or runtime restart and produce one correlated
orchestration receipt without turning WGCF into the aggregate orchestrator.

`delivery.refinement.apply` is the first business workflow after runtime and
definition admission.

## Stage Handoff Checks

The profile is not ready for stage until it proves:

- `active dev-integration profile admission`
- `OOS Temporal adapter and workflow definition contract`
- `namespace and task queue identity boundary`
- `PostgreSQL persistence migration backup and restore`
- `worker and runtime restart replay proof`
- `workflow and activity idempotency retry timeout and cancellation`
- `observability retention and payload redaction`
- `current security acceptance`
- `source projection rollback and suspension proof`

These strings intentionally match `stage_handoff.required_checks` in
`profile.yaml` and must later match the workspace registry.
