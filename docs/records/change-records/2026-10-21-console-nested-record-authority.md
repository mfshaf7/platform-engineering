---
security_evidence:
  review_areas: [delivery, runtime]
  findings: []
  risks: []
  workstreams: [WS-005, WS-007]
---

# Console nested reviewed-record authority parity

## Summary

- Date: 2026-10-21.
- Environment: local dev-integration source repair, not runtime acceptance.
- Severity: complete-runtime activation blocked after normal owner record merge.
- Landing Unit: maintenance-1275-cross-domain-record-parity;
  child_isolated_landing_unit for the Platform owner/rollback boundary.
- Work state: existing Epic1275/qualification1298 and operating-truth candidate;
  approved maintenance, no new repair ART item.

## Classification

- Type: existing runtime source/data admission consumer mismatch.
- User-facing impact: the accepted complete startup fails at its nested
  cross-domain launcher after composition bring-up. No business request is lost.

## Ownership

Platform owns both launchers and their existing bounded record classifier.
Security owns exact-source acceptance. WG owns records and canonical reviewed
registration validation. Console and OOS retain projection/workflow boundaries.

## Root Cause

- Immediate failure: the lower launcher requires exact WG control commit even
  when clean main differs only by the reviewed proposed Intake record.
- Actual root cause: complete-runtime's existing record-only admission was not
  propagated to the generated nested authority binding and its consumer.
- Why it escaped earlier controls: exact-source reader proof stopped at the
  complete coordinator rather than executing the native generated-policy consumer.

## Source Changes

The complete coordinator emits explicit `reviewed-record-only` authority for
WG. The nested launcher reuses `console_record_authority.admit_record_delta`,
including its bounded paths, ancestry, file modes and reviewed registration
companion validation. A descendant must be clean tracked main and contained in
fetched origin/main. Default standalone exact behavior, older explicit minimum
binding and all other owner pins remain unchanged. No broad ancestry waiver,
record rewrite, duplicate admission registry or new workflow is added.

Native real-Git tests execute the complete policy producer and nested source
consumer with an Intake descendant, default exact denial, dirty/non-main and
independent executable/schema/non-descendant rejection. The operator surface
documents the distinction rather than recommending record-by-record repinning.

## Artifact And Deployment Evidence

- Build workflow run: required actual source CI before merge.
- Published image tag/digest: None; host-side launcher source only.
- Recorded prod revision/Argo revision: None; stage/prod are out of scope.

## Host Or Runtime Recovery

Stopped the failing retained supervisor auto-retry after recording the actual
failure. Preserve all owner data, proposed Intake and original Closure request.
This is source mismatch, not corruption, memory pressure or missing permission.
After exact-source acceptance, use the existing complete-runtime activation;
do not hand-edit its generated private policy or skip the lower gate.

## Live Verification

- Local: targeted native suites pass; committed full CI-equivalent and native
  actual-record generated-policy preflight are required before landing.
- Functional: actual original Console request continuation remains required
  after accepted activation; source tests do not grant operating acceptance.
- Residual risk: remaining owner/app transfer qualification is still unfinished.

## Follow-Up

- Required: source review/CI, existing exact-source Security decision/tree and
  generated index, one activation and original Console witness.
- Optional hardening: None proposed in this maintenance.
- Owner: mfshaf7; closure condition: before qualification1298 completes.
