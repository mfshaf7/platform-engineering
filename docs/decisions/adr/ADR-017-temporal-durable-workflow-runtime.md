# ADR-017: Temporal Durable Workflow Runtime

## Status

- Accepted

## Context

Some operator workflows must survive process restarts, external waits,
controlled retries, reconciliation, cancellation, and activity execution across
multiple owners. Synchronous request handling and local session state do not
provide that durability.

The authority split is already defined by workspace governance:

- `operator-orchestration-service` (OOS) owns aggregate workflow behavior
- domain services own bounded activities
- `platform-engineering` owns runtime adoption and lifecycle
- `security-architecture` owns security acceptance
- Governance Operations Console is an OOS client, not a runtime client

The platform needs a replaceable durable runtime without moving business
authority into that runtime or into WGCF.

## Decision

Use Temporal as the proposed durable runtime adapter behind OOS.

- OOS owns versioned workflow definitions, request acceptance, run control,
  correlation, aggregate projection, and final receipts.
- Temporal owns durable scheduling, deterministic replay, timers, persisted
  waits, and activity retry dispatch.
- activity owners retain their domain decisions and expose bounded,
  idempotent operations.
- Governance Operations Console calls OOS only.
- Temporal workflow payloads carry references and bounded decisions, not
  secrets, raw operational context, unbounded artifacts, or duplicate business
  records.
- the first profile is persistent, local-k3s, operator-scoped, and read-only for
  shared smoke.
- normal profile shutdown preserves workflow history; reset is explicit and
  destructive only within the local profile boundary.
- the initial safe proof is `validation-readiness-run`.
- activation-sensitive workflow polling is fenced by a task-queue generation
  derived from the accepted Platform activation-manifest digest; a revoked
  digest cannot be reused for reactivation.
- the first business workflow is `delivery.refinement.apply`.

The initial profile lifecycle is `proposed`. This ADR does not authorize
implementation, launch, stage, or production use.

## Consequences

What becomes simpler:

- long-running workflow state no longer depends on one API process
- retry, timer, wait, and restart semantics have one runtime boundary
- Console and domain authority remain separated from runtime mechanics
- workflow history can be correlated through OOS receipts and projections

What becomes stricter:

- workflow definitions must be reviewed, versioned, and replay-safe
- activities must be idempotent and bounded
- task queues, identities, payloads, retention, and persistence require
  explicit controls
- runtime activation requires Platform and Security admission
- stage and production still require governed release evidence

Required follow-up:

- security and build-admission review
- dev-integration runtime and PostgreSQL implementation
- access, status, smoke, backup, and restore commands
- observability, retention, and version pinning
- restart and deterministic replay proof
- OOS Temporal adapter and initial definition implementation

No change record is required for this ADR because it does not mutate live
runtime state.

## Alternatives Considered

- Keep long-running workflows in synchronous OOS request handlers.
  - Rejected because waits and process restarts would lose durable execution
    state or require a custom workflow engine.
- Make WGCF the aggregate orchestrator.
  - Rejected because WGCF owns governance activities and receipts, not
    cross-domain workflow authority.
- Let Governance Operations Console call Temporal directly.
  - Rejected because it would couple operator UX to runtime mechanics and
    bypass OOS policy, projection, and audit.
- Build a custom durable workflow engine.
  - Rejected because it would duplicate scheduling, replay, timer, retry, and
    persistence machinery without a justified platform advantage.
