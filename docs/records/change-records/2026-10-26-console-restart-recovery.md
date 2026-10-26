---
security_evidence:
  review_areas: [runtime, delivery]
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console restart recovery registration

## Summary

- Date: 2026-10-26
- Short title: Preserve restart recovery through failed-start compensation.
- Environment: Existing local dev-integration composition.
- Severity: Maintenance of failed automatic recovery; no production acceptance claim.

## Classification

- Type: deployment/artifact bug.
- User-facing impact: Console frontend can remain running while composition startup fails and loses its retry service after a PC restart.
- Landing Unit Decision: feature_single_landing_unit; maintenance-console-restart-recovery, same Platform owner, review/deployment and rollback boundary.

## Ownership

- Owning repo or layer: platform-engineering.
- Related repos: security-architecture for exact source/tree acceptance; workspace-governance existing memory learning PR314 for final operating evidence.
- Security review: [Console restart recovery delta](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-10-26-console-restart-recovery.md).
- Related ADR: Existing complete-runtime and dev-integration architecture; no new service, identity or authority boundary.

## Root Cause

- Immediate failure: Boot dependencies were initially unavailable, and later native process faults interrupted composition startup. Underlying memory-access fault cause remains unverified.
- Actual root cause of failed automatic recovery: Successful child down during failed-up compensation was treated as intentional shutdown. It disabled/deleted the controller's own operator-login unit, killed the controller before final state publication and removed automatic retries. This violates the existing runbook rule that failed lifecycle actions preserve recovery registration.
- Why it escaped earlier controls: Previous composition rollback and profile auto-resume cases were verified separately; their parent-action boundary and actual self-termination behavior were not exercised together.

## Source Changes

- Repo: platform-engineering.
- Commit(s): Recorded by the reviewed maintenance PR; source-stage record does not claim operating completion.
- Guardrail added: Parent composition action remains explicit through child compensation. Standalone execution clears stale parent action. Compensation preserves registration; intentional down/reset removal remains intact. Complete-runtime activation waits boundedly for read-only Docker/Kubernetes readiness before effects. Existing owner tests and runbooks cover both boundaries.

## Artifact And Deployment Evidence

- Build workflow run: Full local make validate passed; require exact-head Platform provider CI before merge.
- Published image tag: None; backend image inputs unchanged.
- Published digest: Exact accepted Platform source/tree; Console application artifact unchanged.
- Recorded prod revision: None; local dev-integration only.
- Argo application revision: None.

## Host Or Runtime Recovery

- Required host/runtime action: Exact Security delta/index acceptance, then normal complete-runtime activation and controlled startup/retry/readback proof.
- Why it was environment drift instead of source defect: Initial Docker unavailability and observed process faults were environmental triggers. Loss of recovery registration is a separately reproduced source defect; no hardware cause is asserted.
- Recovery command or procedure: Existing make governance-console-complete-runtime and primary runbook; no new operator command family or service.

## Live Verification

- App health: Final accepted-source proof pending and retained in the existing memory learning closeout; no business history or identity timestamps edited.
- Deployed image: Existing images unchanged.
- Pod: Existing composition participants only.
- Functional verification: Regression reproduced old behavior for manual and automatic compensation. Real systemd isolated fixture showed old controller killed after first attempt with no failure result; corrected source published failure and recovered automatically on attempt2, preserving registration. Explicit down still removed registration. Fixture uses synthetic profile actions, no Kubernetes or business effects; it is not actual PC-reboot or application operating proof.
- Residual risk: A bounded recovery policy cannot guarantee availability during persistent native crashes, absent dependencies or revoked source/identity acceptance. Full startup, native current/history and actual restart observation must remain distinct.

## Follow-Up

- Required follow-up: Source/Security sequence, native acceptance, existing learning PR314 and exact cleanup.
- Optional hardening: None proposed.
- Owner: platform-engineering.
