# Governed Runtime Drill Model

## Purpose

This standard defines the shared enterprise model for temporary runtime drills
that activate, verify, and restore platform or product surfaces without being
mistaken for a governed promotion or a durable live-state change.

Use it when the question is:

- what kind of runtime drill is being performed
- whether the drill is product-only, active-stack, or environment-complete
- which runtime and support surfaces must be included
- what must be captured before activation
- what it means to restore the environment correctly afterward

This standard is about temporary runtime exercise and restoration. It is not
the stage or prod promotion model.

Use these related standards alongside it:

- [governed-release-control-model.md](governed-release-control-model.md)
  for candidate, verification, readiness, and promotion governance
- [governed-runtime-lifecycle-model.md](governed-runtime-lifecycle-model.md)
  for `live`, `traffic-stopped`, `suspended`, and `quarantined`
- [dev-integration-lane.md](dev-integration-lane.md)
  for local source-backed iteration before governed stage rehearsal
- [restart-survival.md](restart-survival.md)
  for routine restart expectations rather than deliberate drill execution

## Core Rule

A runtime drill is not a promotion workflow.

If the operator is exercising a temporary runtime state from local or
pre-release source and intends to return to the prior live posture afterward,
that is a runtime drill and must follow this model.

If the operator is moving an approved candidate toward governed stage or prod
as the new desired state, that is governed promotion and must follow
[governed-release-control-model.md](governed-release-control-model.md) instead.

Do not blur those two workflows in operator docs, evidence, or automation.

## Authority Model

Runtime drills and governed promotion use different sources of truth.

| Authority type | Source of truth | Typical use |
| --- | --- | --- |
| `promotion-governed` | approved Git-managed candidate, readiness decision, and environment contract | normal governed stage rehearsal and prod promotion |
| `runtime-drill` | captured pre-drill baseline plus the scoped local source/runtime activation path | temporary platform or product drill with later restore |

For `runtime-drill` work:

- the drill must capture the current live baseline before activation
- the drill may use local source state or a bounded runtime activation path
- restore must return the in-scope surfaces to that baseline unless an
  explicit reclassification to governed change occurs

## Shared Drill Types

Use these drill types when the workflow is a `runtime-drill`.

| Drill type | Meaning |
| --- | --- |
| `product-runtime-drill` | exercises one product plus the minimum required supporting surfaces |
| `active-stack-runtime-drill` | exercises the current operator-critical mixed-lane stack without claiming estate-complete environment coverage |
| `environment-complete-runtime-drill` | exercises every admitted lane and product environment declared in scope for that environment class |
| `lifecycle-control-drill` | exercises runtime state transitions and bounded control behavior without claiming full functional verification |

Do not call an OpenClaw-only drill an active-stack drill just because it
touches prod.

Do not call a lifecycle-only exercise a product verification pass when it only
proved state transitions.

Reserve the phrase `full platform` for an environment-complete drill or a
clearly declared estate-complete scope.

## Current Active-Stack Scope

The initial `active-stack-runtime-drill` scope for this workspace is:

- `OpenClaw`
- `OpenProject`
- `operator-orchestration-service`
- `Vault`
- `External Secrets`
- `platform-postgresql`
- `Observability`
- `platform-dashboards`
- required host bridge surfaces

This is the minimum current scope for the active operator-critical mixed-lane
stack. A narrower or broader exercise is a different drill type and should be
labeled that way.

The machine-readable profile that enumerates the exact participating surfaces
belongs to the implementation layer. This standard defines the minimum semantic
scope, not the final script payload.

## Current Environment-Complete Scope

The initial `environment-complete-runtime-drill` scope for this workspace is:

- the entire active-stack scope
- prod OpenProject
- the shared non-devint broker lane
- prod platform observability baseline and dashboard overlay
- stage platform observability baseline and dashboard overlay

This is the smallest honest scope that can claim estate-complete coverage for
the currently admitted lanes and product environments.

## Minimum Drill Contract

Every repeatable runtime drill profile should declare at least:

- `authorityType`
- `drillType`
- `targetEnvironment`
- `scope`
- `preconditions`
- `verificationPack`
- `exceptionHandling`
- `restoreMode`
- `restoreScope`
- `evidenceOwner`

The implementation may add more fields, but it should not omit these.

## Baseline Snapshot Requirement

No runtime drill is allowed to start without a pre-drill baseline snapshot.

At minimum, that snapshot must capture the in-scope truth for:

- current Argo applications or equivalent desired-state objects
- lifecycle state objects and pause or skip-reconcile flags
- active namespaces, workloads, and key services
- host bridge or local control services when the drill depends on them
- local repo refs or worktree inputs when local source state is part of the
  drill authority
- release, verification, or readiness objects that the drill will inspect or
  touch

If the operator cannot prove what the pre-drill state was, the restore contract
is already broken and the drill should stop.

## Verification Pack Rule

Each drill must use an explicit verification pack rather than an improvised
list of ad hoc checks.

Each check should resolve to one of:

- `passed`
- `failed`
- `blocked`
- `not_applicable`

If a check is `blocked`, the drill must record one decision path:

- `remove`
- `workaround`
- `accept-risk`
- `defer`

That decision must carry:

- justification
- owner
- review date or follow-up point

This keeps drill execution aligned with real enterprise control rather than
silent operator improvisation.

## Restore Semantics

The default restore mode for every `runtime-drill` is:

- `exact-baseline`

`exact-baseline` means the drill is only complete when the in-scope runtime and
control surfaces are returned to the pre-drill baseline that was captured at
the start.

That restore must cover:

- runtime presence
- lifecycle state
- traffic posture
- reconciliation posture
- scoped host-control surfaces
- any other in-scope support surfaces declared by the drill profile

Restoring only to the current committed GitHub `main` state is not enough when
the pre-drill live posture differed from that state.

If the operator deliberately decides to keep the post-drill state instead of
restoring the baseline, the work is no longer a drill. It must be reclassified
as a governed change and follow the normal approval, rollout, and evidence
path.

## Restore Proof Rule

Restore is not complete from operator intention alone.

The drill must leave enough proof to answer:

- what the baseline was
- what was activated or changed during the drill
- what was restored
- what still differs, if anything
- why any residual difference is acceptable

If a residual difference remains without that explicit reclassification or
exception path, the drill is incomplete.

## Operator Surface Rule

Every repeatable runtime drill needs:

- one machine-readable profile contract
- one primary operator instruction surface

The profile contract belongs with the implementation owner.
The operator instruction surface belongs with the operator workflow owner.

Contracts, scripts, and change records support the workflow, but they do not
replace the primary operator instruction surface.

## Anti-Patterns

These are control failures:

- treating a product-only drill as an active-stack or environment-complete drill
- treating a runtime drill as if it were governed promotion
- starting activation without a baseline snapshot
- restoring only to today's Git `main` instead of the captured live baseline
- leaving broad runtime changes behind and still calling the exercise a drill
- relying on chat memory to reconstruct scope, exceptions, or restore results
