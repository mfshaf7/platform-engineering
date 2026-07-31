# Temporal Operations

## Current Operational Posture

Temporal is build-admitted and has no running platform footprint.

The supported status check is:

```bash
make devint-status PROFILE=temporal
```

Runtime launch, diagnostic access, backup, restore, and workflow execution fail
closed while the profile is build-admitted.

## Implemented Source Boundary

- immutable chart and image pins
- operator-scoped Kubernetes and Temporal namespace rendering
- 10Gi local-path PostgreSQL persistence
- separate runtime, PostgreSQL, OOS, WGCF, and diagnostic identity references
- explicit workflow and activity task queues
- default-deny network policy and no public UI ingress
- reference-only payload and search-attribute allowlists
- read-only smoke, persistent suspend, explicit backup and restore, and
  confirmed destructive reset
- quiesced two-database backup with state-preserving completion and fail-safe
  restore behavior
- digest-pinned workflow-generation retirement manifest issuance and OOS
  receipt verification

## Activation Checks

Before the profile becomes `active`, prove:

- owner runtime commands are runnable against the controlled runtime
- PostgreSQL migration, persistence, backup, restore, and reset behavior
- runtime and OOS worker restart survival
- deterministic replay compatibility
- workflow and activity idempotency
- retry, timeout, cancellation, and suspension behavior
- namespace and task-queue identity isolation
- metrics, logs, traces, retention, and redaction
- current security acceptance

## Initial Runtime Proof

The first controlled execution is `validation-readiness-run`. Its workflow
worker polls only the queue generation derived from the currently accepted
activation-manifest digest. A revoked digest is never reused; a fresh
activation therefore cannot execute a late start retained on an older queue.

It must:

- use an OOS-owned versioned definition
- invoke only bounded WGCF readiness activity
- survive a runtime or worker restart
- preserve one correlation chain
- produce the expected orchestration receipt
- remain local dev-integration evidence

The first business workflow, `delivery.refinement.apply`, follows only after
the safe proof and definition admission pass.

## Planned Generation Retirement

Do not use activation-evidence removal as a cleanup mechanism. An unexpected
loss makes the ordinary OOS worker fail-stop with an incomplete fence; it does
not authorize polling the old queue or claim its executions are retired.

For a planned retirement:

1. quiesce OOS start ingress
2. prove start-ingress replicas and in-flight starts are both zero
3. scale ordinary OOS workflow pollers to zero and retain that evidence
4. issue the old generation's manifest with
   `generation_retirement.py issue`
5. mount the manifest read-only for the OOS `retire` one-shot command and pass
   its exact digest
6. retain the emitted receipt and run
   `generation_retirement.py verify-receipt`
7. issue no fresh activation until the verifier returns `accepted`

The issuer requires explicit timestamps, evidence references, and zero counts;
it derives the queue from the pinned activation-manifest digest and writes a
mode-0600 JSON file atomically. Drain observations must be no more than five
minutes old and the manifest lifetime cannot exceed fifteen minutes. The
verifier rejects future receipt times, mismatched targets, digests, queues,
drain evidence, cancellation and terminal counts, or fewer than seven
post-stop empty scans. It also requires the OOS one-shot start timestamp to
fall inside the manifest lifetime while allowing a valid drain to complete
after that authorization window.

This operator surface is source-valid now. It does not make the build-admitted
profile launchable and must not be used as evidence that a retirement run has
already occurred.

## Common Failure Signals

- proposed or build-admitted profile is treated as launchable
- Console or another caller attempts direct Temporal access
- OOS and an activity owner disagree on workflow ownership
- workflow payload contains secrets, raw context, or unbounded artifacts
- worker restart loses progress or duplicates a non-idempotent effect
- task queues allow the wrong worker boundary
- profile shutdown destroys persistent history
- a fresh activation is issued without the prior generation's accepted
  retirement receipt

## First Response

1. stop new workflow starts through OOS
2. preserve workflow and platform evidence
3. classify the failure as runtime, workflow definition, activity, identity,
   persistence, or projection
4. repair the owning boundary
5. replay or retry only through the admitted OOS control

## Evidence To Capture

- exact OOS definition id and version
- Temporal and worker source or image versions
- namespace and task queue
- run, correlation, and causation references
- restart and replay outcome
- activity and final receipt references
- persistence and restore evidence
- security review reference
- start-ingress and ordinary-poller drain evidence references
- retirement manifest and receipt digests

## Related Procedures

- [README.md](README.md)
- [architecture.md](architecture.md)
- [release-governance.md](release-governance.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
