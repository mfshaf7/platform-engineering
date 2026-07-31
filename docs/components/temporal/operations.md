# Temporal Operations

## Current Operational Posture

Temporal is proposed and has no running platform footprint.

After the workspace profile registry lands, the supported status check is:

```bash
make devint-status PROFILE=temporal
```

All runtime-mutating profile scripts fail closed in the proposed lifecycle.

## Build-Admission Checks

Before implementation begins, confirm:

- Platform accepts the persistent local-k3s runtime shape.
- Security review covers identity, task queues, secrets, persistence, network
  exposure, UI access, and workflow payload boundaries.
- OOS owns the Temporal client, workers, definitions, run control, and
  aggregate projection.
- activity owners expose bounded and idempotent operations.
- normal suspend preserves workflow history.
- reset is explicit, local, and destructive only within the profile boundary.
- shared smoke remains read-only.

## Activation Checks

Before the profile becomes `active`, prove:

- owner runtime commands are implemented and runnable
- PostgreSQL migration, persistence, backup, restore, and reset behavior
- runtime and OOS worker restart survival
- deterministic replay compatibility
- workflow and activity idempotency
- retry, timeout, cancellation, and suspension behavior
- namespace and task-queue identity isolation
- metrics, logs, traces, retention, and redaction
- current security acceptance

## Initial Runtime Proof

The first controlled execution is `validation-readiness-run`.

It must:

- use an OOS-owned versioned definition
- invoke only bounded WGCF readiness activity
- survive a runtime or worker restart
- preserve one correlation chain
- produce the expected orchestration receipt
- remain local dev-integration evidence

The first business workflow, `delivery.refinement.apply`, follows only after
the safe proof and definition admission pass.

## Common Failure Signals

- proposed or build-admitted profile is treated as launchable
- Console or another caller attempts direct Temporal access
- OOS and an activity owner disagree on workflow ownership
- workflow payload contains secrets, raw context, or unbounded artifacts
- worker restart loses progress or duplicates a non-idempotent effect
- task queues allow the wrong worker boundary
- profile shutdown destroys persistent history

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

## Related Procedures

- [README.md](README.md)
- [architecture.md](architecture.md)
- [release-governance.md](release-governance.md)
- [../../runbooks/dev-integration-profiles.md](../../runbooks/dev-integration-profiles.md)
