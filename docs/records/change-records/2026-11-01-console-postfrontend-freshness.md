---
security_evidence:
  review_areas: [runtime, delivery]
  reviewed_artifacts:
    - products/governance-operations-console/scripts/console_complete_runtime.py
    - products/governance-operations-console/scripts/test_console_complete_runtime.py
    - products/governance-operations-console/runbooks/operate-complete-runtime.md
  findings: []
  risks: []
  workstreams: [WS-003, WS-005]
---

# Console final startup source freshness

## Summary

- Date: 2026-11-01
- Short title: Re-observe canonical source after potentially slow startup work.
- Environment: Existing local complete-runtime composition.
- Severity: Owner maintenance; no new authority or production acceptance.

## Classification

- Type: deployment/artifact bug.
- User-facing impact: A newly started frontend can correctly deny source-dependent operations because the startup checkpoint expired during preparation.
- Landing Unit Decision: feature_single_landing_unit.
- Landing Unit: maintenance-console-postfrontend-freshness.
- Work home: Operator-authorized maintenance without new ART or improvement records.

## Ownership

- Owning repo or layer: platform-engineering, existing complete-runtime lifecycle.
- Related repos: Security Architecture for exact source/tree acceptance; existing record owners remain authoritative.
- Related ADR: Existing complete-runtime and source-freshness contracts; no new component or workflow.
- Security review: [Console batch and startup boundary](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/components/2026-11-01-console-ui-batch-two.md).

## Root Cause

- Immediate failure: Final readiness at 2026-11-01T11:51:22Z rejected an unavailable canonical record checkpoint; native preparation retained historical requests while current source was unavailable.
- Actual root cause: Startup refreshed after composition, before identities, frontend preparation, artifact confirmation and provider setup. These remaining steps could exceed the unchanged five-minute source window. The frontend-start stage began at 11:45:33Z; final readiness only began at 11:50:43Z.
- Why it escaped earlier controls: The existing activation ordering case made frontend and finishing effects instantaneous, so it could not expose expiry across those effects.

## Source Changes

- Repo: platform-engineering.
- Commit(s): Exact Gary candidate, review and merge are retained in the resulting PR and paired Security source selection.
- Guardrail added: Extend the existing lifecycle test with warm, cold, late-finishing and unavailable-provider cases. Repeat the existing authoritative refresh immediately before final readiness, after all potentially long startup work.
- Source expiry, trusted owner validation, credentials, operator decisions and effect scopes remain unchanged. No source success is inferred from a running frontend.

## Artifact And Deployment Evidence

Source-only ordering repair. No image, data schema, package, model, root helper or installed policy changes. Runtime selection remains subject to exact composed Security acceptance.

## Host Or Runtime Recovery

- Required host/runtime action: Normal accepted complete-runtime activation and status.
- Why it was environment drift instead of source defect: Not environment drift; the lifecycle failed to renew its own bounded source evidence after potentially slow work.
- Recovery command or procedure: Existing [complete-runtime runbook](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md). Preserve owner records and original activation generation.

## Live Verification

- App health: The previously selected frontend started and authenticated identity/Model reads passed; source-dependent preparation withheld new inputs. This is not full operating success.
- Deployed image: Unchanged by this source-only repair.
- Pod: Existing composition; no new workload.
- Functional verification: The previous implementation fails the cold-frontend expiry case; final lifecycle cases must pass before publication. Normal exact-source activation and fresh native reads remain required after acceptance.
- Residual risk: An unavailable owner/provider still blocks final readiness; this repair does not relax or extend evidence lifetime.

## Follow-Up

- Required follow-up: Green exact-head owner checks, paired Security source/tree and generated-index update, normal activation and native readback before closure.
- Optional hardening: None added by this repair.
- Owner: Platform Engineering and Security Architecture within this maintenance release.
