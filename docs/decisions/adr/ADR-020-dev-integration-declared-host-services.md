# ADR-020: Dev-Integration Declared Host Services

## Status

- Accepted

## Context

The shared dev-integration runner executes each profile action in a temporary
process group and terminates that group when the action completes. This is the
correct fail-closed behavior for ordinary action descendants.

Some active profiles also require a host-side reconciler or bridge to remain
alive after `up` returns. Backgrounding that process inside `up.sh` conflicts
with action cleanup, while allowing profile scripts to escape with `setsid`
would create an untracked lifecycle outside the session manifest. A user
systemd manager is not available on every supported workstation, and moving
host-bound work into Kubernetes would lose required host repo and CLI access.

## Decision

Extend the existing platform-owned dev-integration runner with an explicit
`host_services` profile contract.

The shared runner:

- validates owner-relative service and readiness commands
- derives a source-bound command digest
- launches the foreground service through runner-owned detachment
- records PID and Linux process-start identity before treating it as owned
- waits for explicit process or command readiness
- reconciles idempotently on `up`
- reports truthful state on `status`
- stops the verified process group on `down` and `reset`
- refuses to kill or replace an identity-mismatched PID

Profile owners provide service behavior and readiness semantics but do not own
backgrounding, PID files, logs, or teardown. Undeclared action descendants
continue to be terminated by the existing action process-group boundary.

## Consequences

- Persistent host-side support becomes visible, testable, and reusable across
  profiles without introducing another control plane.
- Session manifests can report exact local service identity and readiness.
- The runner remains Linux/WSL-specific for this capability because it binds
  `/proc` process-start identity and POSIX process groups.
- Profile migrations must remove prior `nohup`, PID, and stop implementations
  rather than running both lifecycle models.
- Source validation and local runtime proof remain required before a profile
  can claim the new lifecycle works.
- Governed stage or production service management remains out of scope.

The source implementation and local proof are recorded in
[the corresponding change record](../../records/change-records/2026-08-24-devint-host-service-supervision.md).

## Alternatives Considered

- User systemd unit:
  - rejected because the supported workstation does not guarantee an available
    user manager or lingering session
- Kubernetes CronJob or Deployment:
  - rejected because the immediate reconciler needs host-mounted repos and the
    host `k3s kubectl` execution boundary
- Profile-owned `nohup` or `setsid` escape:
  - rejected because it bypasses runner identity, status, evidence, and cleanup
- Removing action process-group cleanup:
  - rejected because it would permit undeclared background descendants to leak
