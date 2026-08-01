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

The source-valid generation-retirement operator is also available for evidence
preparation and receipt verification. It does not launch Temporal or OOS:

```bash
python3 dev-integration/profiles/temporal/scripts/generation_retirement.py --help
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
issued manifest and digest.

Planned retirement is ordered rather than inferred from activation-evidence
loss. Platform first drains OOS start ingress and proves zero active replicas
and zero in-flight starts. It then proves zero ordinary OOS workflow pollers
and issues a manifest lasting no more than fifteen minutes, using drain
observations no more than five minutes old, pinned to the old activation
digest, business queue, generation start registry, Temporal target, and both
drain evidence references. It also pins the OOS Ed25519 receipt verifier. The
ordinary OOS process serves both generated queues continuously, and each
business start registers through Update-with-Start before it can start. The
workflow enforces one deterministic Update ID per business workflow, so retries
do not grow accepted history. OOS caps a generation at 512 registrations and
returns `409 orchestration_generation_capacity_exhausted` when rotation is
required. It verifies its receipt key before mutation, carries the manifest
lifetime in the seal signal, validates handler time before closing the durable
registry, and reconciles its exact workflow IDs. OOS alone runs the one-shot
cancellation and drain worker. Platform verifies the
receipt signature and retains the OOS receipt before any fresh activation can
be issued. The manifest pins the exact canonical JSON and signed-content
contract, and both repos prove it with the same byte vector. A post-seal retry
uses an explicit refreshed manifest bound to the
exact prior seal authorization. An expired signal leaves the registry open for
a fresh authorized seal. Temporal Visibility remains diagnostic only.
Unexpected evidence loss makes the ordinary worker fail-stop and never counts
as a retirement receipt.

The workflow must prove durability across worker or runtime restart and produce
one correlated orchestration receipt without turning WGCF into the aggregate
orchestrator.

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
