---
security_evidence:
  review_areas: [runtime]
  findings: []
  risks: []
  workstreams: [WS-007]
  reviewed_artifacts:
    - security-architecture/docs/reviews/components/2026-10-15-governance-console-platform-operation.md
  notes: "Version-only host drift correction; exact composed Security acceptance and index follow the actual owner merge. No operating acceptance is claimed by source validation."
---

# Align existing bindings with installed Ollama 0.40.8

## Summary

- Date: 2026-10-23
- Short title: existing provider runtime patch alignment
- Environment: local dev-integration
- Severity: accepted composition startup blocked

## Classification

- Type: environment metadata/pin drift
- User-facing impact: gateway refuses readiness because installed0.40.8 does
  not match the accepted0.40.7 exact runtime binding

## Ownership

- Owning repo or layer: platform-engineering
- Related repos: security-architecture; existing Epic1275 acceptance1298
- Related ADR: existing governed model-profile/access-plane boundary; unchanged

## Root Cause

- Immediate failure: provider-integrity-failed on all six selected profiles
- Actual root cause: Windows provider patch advanced beyond reviewed pins
- Why it escaped earlier controls: live provider version was checked during
  activation rather than refreshed before final exact-source acceptance

## Source Changes

- Repo: platform-engineering
- Commit(s): pending Agent Gary exact-head review at authoring
- Guardrail added: none; retain existing exact runtime/model checks
- Change: only the six existing runtime_version values0.40.7 to0.40.8
- Test: current profile/lifecycle/access-plane validators and complete local CI
- Runbook: reuse operate-complete-runtime.md installed-version procedure
- No model, digest, task, caller, permission, gateway code or update policy change

## Artifact And Deployment Evidence

- Build workflow run: pending exact committed local/provider CI
- Published image tag: None
- Published digest: None
- Recorded prod revision: None
- Argo application revision: None

## Host Or Runtime Recovery

- Required host/runtime action: normal composed activation after actual source
  merge and exact composed Security acceptance/index refresh
- Why it was environment drift instead of source defect: installed provider
  advanced; the existing integrity guard correctly rejects a different version
- Recovery command or procedure: existing complete-runtime ACTION=activate
- No host downgrade, model download, integrity waiver or update-policy change

## Live Verification

- App health: not claimed; original Console journey remains required
- Deployed image: None changed by this source record
- Pod: actual gateway readiness reported provider-integrity-failed
- Functional verification: Windows /api/version0.40.8; /api/tags qwen3:8b
  digest500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
- Residual risk: future installed patch changes still require explicit exact
  acceptance; automatic update policy remains an operator decision

## Follow-Up

- Required follow-up: recheck live provider version/digest before final Security
  acceptance and activation; prove actual runtime readiness and original journey
- Optional hardening: none introduced during this version-only correction
- Owner: Platform; Security retains exact-source acceptance authority
