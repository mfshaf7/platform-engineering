---
security_evidence:
  review_areas: [runtime]
  reviewed_artifacts:
    - products/governance-operations-console/scripts/console_observation_refresh.py
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/scripts/test_console_complete_runtime.py
    - products/governance-operations-console/runbooks/operate-complete-runtime.md
  findings: []
  risks: []
  workstreams: [WS-005]
---

# Coordinate lifecycle and runtime observation collection

## Summary

Normal Console activation and restart wait for an existing runtime observation
collector instead of failing healthy startup because its private lock is busy.

## Classification

Operator-authorized maintenance of the current recovery path, outside active
ART scope. Landing Unit decision: `feature_single_landing_unit`,
`maintenance-observation-lifecycle-lock`.

## Ownership

Platform owns the existing collector,
lifecycle commands and [operator procedure](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md).

## Root Cause

After the November 3 restart, all five composition participants started. Final
activation then failed with `Runtime observation refresh is already running.`
The existing independent timer and activation used the same nonblocking lock.
The collector correctly denied concurrent publication, but lifecycle code
treated this expected overlap as startup failure. Temporarily stopping only
the timer contained the collision while normal startup retried.

## Source Changes

Reuse the same private exclusive lock. Activation and restart wait for its
current owner to finish before performing their own fresh collection. Periodic
collection remains nonblocking. Lock custody, admitted reader commands, atomic
publication, collection failure, source freshness and existing service/lifecycle
deadlines remain authoritative. No healthy timestamp or readiness result is
manufactured from a busy lock, and no scheduler, service or operator command is
added.

Synthetic lifecycle test policies use a temporary private state root so catalog
fixtures cannot inherit the operator's real recovery latch. Runtime recovery
checks remain unchanged. The existing lifecycle CI test entrypoint includes the
collector regressions through its shared collector fixture.

## Security Evidence

This is coordination within the existing private runtime observation boundary;
it adds no principal, permission, workload command, data source or privilege.
The concrete [composed Console review](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-24-configurable-ai-routing.md)
continues to govern these unchanged boundaries. No registered Platform delta
trigger matches these product-local paths. Exact merged source/tree acceptance
and the generated owner-record index must land before activating this revision.

## Artifact And Deployment Evidence

Publish the isolated maintenance source through Gary and delegated accountable
review. Final composed acceptance binds the actual merged source and tree;
the Security owner-record index follows the merged change record.

## Live Verification

Qualification uses a real competing filesystem lock: lifecycle collection waits
without reading or publishing, then produces fresh evidence after release.
Collection failure after waiting still preserves previous evidence and releases
the lock; default periodic overlap still fails before collection. Run existing
collector/lifecycle tests and owner structure, governance and operator checks.
Final proof requires the accepted native runtime with its ordinary timer active.

## Follow-Up

Complete accepted native verification with the ordinary timer active. Rollback
restores the prior reviewed Platform source and matching composed acceptance.
Do not weaken freshness/custody or label an incomplete activation healthy.
