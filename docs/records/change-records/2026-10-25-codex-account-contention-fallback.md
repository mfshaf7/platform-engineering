---
security_evidence:
  review_areas: [identity, secrets, runtime, ai]
  reviewed_artifacts:
    - dev-integration/profiles/governed-ai-gateway/runtime/model_management.py
    - scripts/test_ai_task_routing.py
    - products/governance-operations-console/runbooks/operate-complete-runtime.md
  findings: []
  risks: []
  workstreams: [WS-007]
  notes: Classify only account projection entry contention before inference; retain native account serialization, explicit fallback permissions and post-submission uncertainty.
---

# Codex account contention and explicit fallback

## Summary

- Date: 2026-10-25
- Short title: Preserve configured fallback when native account admission is busy
- Environment: local dev-integration
- Severity: corrective maintenance in existing Epic1313 qualification1321

## Classification

- Type: existing provider-adapter admission classification bug
- User-facing impact: a distinct concurrent Codex request could be mistaken for an already running invocation, preventing the configured local fallback

## Ownership

- Owning repo or layer: platform-engineering
- Related repos: security-architecture and workspace-governance
- Related ADR: ADR-030 configurable AI task routing

## Root Cause

- Immediate failure: an actual independent intake request returned409 invocation-in-progress while a separate real Codex source-profile turn completed200 under configuration13
- Actual root cause: account projection acquired its own nonblocking filesystem mutex before dispatch, but raw BlockingIOError escaped the selected adapter and was mistaken for the invocation journal's own lock contention
- Why it escaped earlier controls: provider-error tests injected typed availability errors; actual local-to-Codex fallback did not exercise the reverse native account admission path

## Source Changes

- Repo: platform-engineering; maintenance Landing Unit delivery-1313-codex-account-contention
- Commit(s): exact reviewed Gary candidate and eventual merge are supplied by source publication
- Guardrail added: actual account projection/flock through the routed gateway verifies configured fallback, fail-closed exhaustion and original-result replay; separate dispatch and context-exit errors must not be reclassified as pre-submission busy

Only entering the account projection maps contention to existing ProviderBusy.
ExitStack keeps dispatch, persistence and context-exit failures outside that
catch. No new lock, caller, model, data scope, authority or fallback policy is
introduced, and original uncertain invocation identities are not retried.

## Artifact And Deployment Evidence

- Build workflow run: exact committed owner CI-equivalent proof and provider CI are required before merge
- Published image tag: existing governed-ai-runtime publication path after exact Security acceptance
- Published digest: supplied by the normal accepted image publication/commissioning receipt
- Recorded prod revision: None; this is dev-integration qualification
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: reconcile the accepted gateway image and frozen final source set through existing complete-runtime activation
- Why it was environment drift instead of source defect: not applicable; the adapter classification is a source defect
- Recovery command or procedure: operate-complete-runtime; land owner, Security and learning records before the final composition activation

## Live Verification

- App health: existing real consumer proofs are retained; final current readback remains1321 operating work
- Deployed image: exact accepted runtime image from normal commissioning is required
- Pod: actual native gateway owner readback, not a guessed deployment revision
- Functional verification: the actual account-mutex regression reproduces the original409; the correction passes25 focused tests, including fallback, exhaustion, frozen replay and post-dispatch non-reclassification
- Residual risk: owner tests and source acceptance do not claim live provider entitlement or final operating completion

## Follow-Up

- Required follow-up: exact source/Security acceptance, image qualification and actual Codex-to-local plus no-fallback proof; retain the old409 identity as uncertain rather than silently dispatching it again
- Optional hardening: None; extend the existing boundary without another control plane or ART child
- Owner: platform-engineering; the existing1321 blocker and linked regression candidate retain closure truth
