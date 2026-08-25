# Governed AI Work Design Profile Foundation

## Summary

- Date: 2026-08-25
- Short title: Multi-profile gateway and inactive Work Design registration
- Environment: platform source control and local dev-integration rendering
- Severity: Medium

## Classification

- Type: platform governance source foundation
- User-facing impact: Prepares one typed, fail-closed Work Design assist path
  without activating model use or changing canonical workflow truth.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`, `context-governance-gateway`,
  `security-architecture`
- Related architecture: Workspace Delivery ART #884 architecture packet v9
- Related ADR:
  `docs/decisions/adr/ADR-021-multi-profile-governed-ai-gateway.md`

## Root Cause

- Immediate failure: The gateway runtime could resolve only one globally active
  logical profile and its provider adapter embedded intake-specific behavior.
- Actual root cause: Profile selection, task identity, strict output validation,
  and activation were not independently represented per logical profile.
- Why it escaped earlier controls: The first runtime intentionally proved only
  the intake classifier. Work Design introduced the first second consumer and
  exposed the single-profile assumption.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): finalized Review Packet for ART #992 records the merged commit.
- Guardrails added:
  - complete registry resolution with per-profile activation state
  - exact caller, task, contract version, input, and output-schema enforcement
  - strict schema validation independent of provider formatting behavior
  - static runtime modules instead of Bash-generated application source
  - compatibility tests for the existing intake response
  - provider non-invocation proof for inactive Work Design requests

## Artifact And Deployment Evidence

- Build workflow run: recorded by the ART #992 Review Packet.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Live Verification

- App health: Not applicable; this work does not activate or deploy the Work
  Design profile.
- Functional verification:
  - `python3 scripts/validate_ai_model_profiles.py`
  - `python3 scripts/test_ai_model_profiles.py`
  - `python3 scripts/test_governed_ai_gateway_policy.py`
  - `python3 scripts/test_governed_ai_gateway_runtime.py`
  - `python3 scripts/test_governed_ai_ollama_adapter.py`
  - `python3 scripts/test_dev_integration.py`
- Residual risk: Work Design provider invocation remains unavailable until the
  later Security review and explicit activation work pass.

## Follow-Up Actions

- Required follow-up: ART #993 integrates OOS and CGG against the inactive
  typed contract without enabling provider access.
- Required follow-up: ART #994 performs the Security review.
- Required follow-up: ART #995 may activate Work Design only after the prior
  integration and Security evidence pass.
- Owner: Platform Engineering, OOS, CGG, and Security Architecture according to
  their existing boundaries.
