---
security_evidence:
  review_areas:
    - identity
    - secrets
    - delivery
    - ai
  findings:
    - F-007
  risks:
    - R-007
  workstreams:
    - WS-007
---

# Governed AI Intake Foundation

## Summary

- Date: 2026-04-18
- Short title: platform-owned governed AI intake foundation
- Environment: none
- Severity: medium

## Classification

- Type:
  - platform contract and governance model
- User-facing impact:
  - none yet; this adds the reviewed control model for future governed
    AI-assisted intake

## Ownership

- Owning repo or layer: platform-engineering
- Related repos:
  - security-architecture
  - workspace-governance
- Related ADR:
  - ADR-012-governed-ai-access-plane-and-model-profiles.md

## Root Cause

- Immediate failure:
  - the workspace had no platform-owned way to tell whether an AI-assisted
    intake suggestion came from a governed model or only from an ad hoc model
    invocation
- Actual root cause:
  - governed AI status was not previously defined as approved profile plus
    governed invocation path
- Why it escaped earlier controls:
  - prior AI governance work was baseline-only and did not yet define the
    platform-owned profile registry or intake-specific approval rule

## Source Changes

- Repo:
  - platform-engineering
- Commit(s):
  - pending merge at review time
- Guardrail added:
  - standard
  - validator
  - ADR

## Artifact And Deployment Evidence

- Build workflow run:
  - None
- Published image tag:
  - None
- Published digest:
  - None
- Recorded prod revision:
  - None
- Argo application revision:
  - None

## Host Or Runtime Recovery

- Required host/runtime action:
  - None
- Why it was environment drift instead of source defect:
  - not applicable
- Recovery command or procedure:
  - None

## Live Verification

- App health:
  - None
- Deployed image:
  - None
- Pod:
  - None
- Functional verification:
  - `python3 scripts/validate_ai_model_profiles.py`
  - `python3 scripts/validate_governance_docs.py --repo-root .`
  - `python3 scripts/validate_repo_structure.py --repo-root .`
- Residual risk:
  - the approved intake classifier profile remains suspended until the governed
    AI gateway and runtime enforcement path are real

## Follow-Up

- Required follow-up:
  - implement the internal AI gateway and activate the intake-classifier
    profile only after audit and egress controls are live
- Optional hardening:
  - add operator-facing status reporting for active and suspended governed AI
    profiles
- Owner:
  - platform-engineering
