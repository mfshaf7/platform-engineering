---
security_evidence:
  review_areas:
    - identity
    - secrets
    - delivery
    - runtime
    - ai
  findings:
    - F-007
  risks:
    - R-007
  workstreams:
    - WS-007
---

# Governed AI Runtime Assist Contract

## Summary

- Date: 2026-04-29
- Short title: Governed AI runtime assist activation contract
- Environment: platform source control
- Severity: Medium

## Classification

- Type: platform governance contract
- User-facing impact: Prevents bounded AI runtime assists from being treated as
  governed until the platform profile, invocation, audit, approval, activation,
  and rollback gates are proven.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `security-architecture`, `workspace-governance`
- Related ADR: `docs/decisions/adr/ADR-012-governed-ai-access-plane-and-model-profiles.md`

## Root Cause

- Immediate failure: Delivery `#251` needed a concrete platform contract before
  bounded runtime-assist consumers could be implemented or activated.
- Actual root cause: The profile registry and AI access model documented the
  control posture, but no machine-readable runtime-assist activation contract
  bound profile selection, audit fields, approval boundaries, environment gates,
  and rollback controls together.
- Why it escaped earlier controls: Earlier work intentionally parked live AI
  runtime activation behind suspended profiles and security review, so the
  activation contract was not required until this delivery slice.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): pending PR merge
- Guardrail added: validator
- Guardrail added: standard
- Guardrail added: security-reviewed change record

## Artifact And Deployment Evidence

- Build workflow run: Not applicable; source-only governance contract.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Host Or Runtime Recovery

None.

## Live Verification

- App health: Not applicable; no runtime deployment.
- Deployed image: Not applicable.
- Pod: Not applicable.
- Functional verification: `python3 scripts/validate_ai_model_profiles.py --repo-root .`
- Residual risk: Live activation remains blocked until the governed access
  plane, caller identity, audit retention, provider-egress block, and fresh
  security delta review are proven.

## Follow-Up

- Required follow-up: Land the security delta review for `#254/#350/#351`, then
  implement the governed access-plane prerequisite before any profile activation.
- Optional hardening: Add CI enforcement for cross-repo profile consumers once a
  runtime consumer is merged.
- Owner: Platform Engineering / Security Architecture
