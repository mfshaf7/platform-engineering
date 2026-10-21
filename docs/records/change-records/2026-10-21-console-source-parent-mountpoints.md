---
security_evidence:
  review_areas: [delivery, runtime]
  workstreams: [WS-005, WS-007]
  reviewed_artifacts:
    - docs/reviews/components/2026-10-15-governance-console-platform-operation.md
  notes: Exact reserved child mountpoints in the existing sanitized read-only source parent; no new source authority.
---

# Preserve reviewed child mounts beneath the source parent

## Summary

- Date: 2026-10-21
- Short title: Prepare the existing read-only nested source mount topology.
- Environment: Local dev-integration only.
- Severity: Activation blocker; no canonical admission occurred.

## Classification

- Type: deployment/artifact bug
- User-facing impact: Complete Console activation cannot start the updated WGCF API.

## Ownership

- Owning repo or layer: Platform Engineering, complete Console runtime.
- Related repos: WGCF, Console, Security Architecture.
- Related ADR: Existing complete-runtime composition; no new architecture.

## Root Cause

- Immediate failure: OCI cannot create the Console child mountpoint inside the read-only source parent.
- Actual root cause: The sanitized source parent excluded the existing reviewed roots without reserving their empty mount directories.
- Why it escaped earlier controls: The native image proof mounted the parent alone, not the actual parent-plus-children topology.

## Source Changes

- Repo: platform-engineering
- Commit(s): This reviewed Landing Unit; actual merge is recorded by the provider.
- Guardrail added: Exactly three empty, owned, regular directories survive refresh; symlinks, files and non-empty directories are preserved and denied. Unit tests and opt-in native OCI regression cover repeated refresh, unsafe targets and all read-only nested mounts at UID10001.

## Artifact And Deployment Evidence

- Build workflow run: Exact-head provider CI required before merge.
- Published image tag: None; Platform source preparation only.
- Published digest: None.
- Recorded prod revision: None; no production change.
- Argo application revision: None.

## Host Or Runtime Recovery

- Required host/runtime action: Reaccept the actual Platform merge and run normal complete-runtime activation once.
- Why it was environment drift instead of source defect: Not environment drift; source omitted required mount targets.
- Recovery command or procedure: Existing complete-runtime operator runbook; no live patch, writable parent, global source mount or data reset.

## Live Verification

- App health: Pending actual accepted activation; source tests are not operating proof.
- Deployed image: Existing exact accepted WGCF source.
- Pod: Rediscover from the actual deployment during activation.
- Functional verification: Disposable native nested read-only mount proof before publication; full actual nested Security reader and current runtime readback after commissioning.
- Residual risk: Little List admission, Inventory, app delivery and final exercise remain uncompleted; this repair claims none of them.

## Follow-Up

- Required follow-up: Actual Security acceptance/index and normal commissioning, then the original Console workflow.
- Optional hardening: None added outside the current repair.
- Owner: Platform Engineering.
