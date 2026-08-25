# Refinement Runtime Profile Foundation

## Summary

- Date: 2026-08-26
- Short title: Inactive Refinement advisor and durable apply registrations
- Environment: platform source control and local dev-integration rendering
- Severity: Medium

## Classification

- Type: platform governance source foundation
- User-facing impact: Prepares typed Refinement AI advice and durable apply
  runtime bindings without activating either path or changing Console behavior.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`,
  `context-governance-gateway`, `security-architecture`
- Related architecture: Workspace Delivery ART #909 architecture packet v17
- Related ADR:
  `docs/decisions/adr/ADR-017-temporal-durable-workflow-runtime.md`

## Root Cause

- Immediate failure: Refinement contracts had no independently resolvable
  provider profile or durable apply runtime binding.
- Actual root cause: OOS semantic contracts landed before their Platform-owned
  provider, queue, worker, egress, and activation boundaries were registered.
- Why it escaped earlier controls: Work Design and intake were the only active
  consumers; Refinement is the first selected-not-active consumer spanning both
  governed AI and Temporal profiles.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): finalized Review Packet for ART #1007 records the merged commit.
- Guardrails added:
  - exact caller, task, schema, queue, worker, and OOS contract bindings
  - independent selected-not-active lifecycle validation
  - provider non-invocation and worker-start denial
  - direct Console, consumer credential, and Platform business-logic denials
  - compatibility coverage preserving existing intake and Work Design behavior

## Artifact And Deployment Evidence

- Build workflow run: recorded by the ART #1007 Review Packet.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Live Verification

- App health: Not applicable; this work does not activate or deploy either
  Refinement profile.
- Functional verification:
  - `python3 scripts/validate_ai_model_profiles.py`
  - `python3 scripts/test_ai_model_profiles.py`
  - `python3 scripts/test_governed_ai_gateway_policy.py`
  - `python3 scripts/test_governed_ai_gateway_runtime.py`
  - `python3 scripts/test_governed_ai_ollama_adapter.py`
  - `python3 scripts/test_dev_integration.py`
  - `python3 dev-integration/profiles/temporal/scripts/validate_source.py`
- Residual risk: Both profiles remain unavailable until Security review #1012
  and Platform activation #1013 pass.

## Follow-Up Actions

- Required follow-up: ART #1009 implements OOS Refinement runtime behavior.
- Required follow-up: ART #1012 performs the Security review.
- Required follow-up: ART #1013 may activate the profiles only after the
  integration and Security evidence pass.
- Owner: OOS, Security Architecture, and Platform Engineering according to
  their existing boundaries.
