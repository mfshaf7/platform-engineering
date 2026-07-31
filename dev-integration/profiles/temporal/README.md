# Temporal Dev-Integration Profile

This is the proposed persistent local-k3s profile for the platform-owned
Temporal runtime behind `operator-orchestration-service` (OOS).

The profile is structurally complete for review but is not implementation
authorization. It cannot launch a runtime until Platform and Security gates
move it through `build-admitted` to `active`.

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

## Current Operator Actions

After the workspace registry records the proposed profile, status inspection is
allowed:

```bash
make devint-status PROFILE=temporal
```

Runtime actions remain denied:

```bash
make devint-up PROFILE=temporal
make devint-access PROFILE=temporal
make devint-smoke PROFILE=temporal
make devint-down PROFILE=temporal
make devint-reset PROFILE=temporal
make devint-promote-check PROFILE=temporal
```

## Initial Proof

The first controlled workflow is `validation-readiness-run`. It must prove
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
