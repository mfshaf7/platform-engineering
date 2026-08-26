# Refinement Catalog Platform Activation

## Summary

- Date: 2026-08-26
- Short title: Activate bounded Refinement advice and durable apply in dev-integration
- Environment: local `dev-integration`
- Severity: Medium

## Classification

- Type: platform governance activation
- User-facing impact: Enables the reviewed OOS Refinement and Catalog runtime
  through the registered composition without enabling Console integration,
  direct browser access, paid providers, stage, or production.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`, `context-governance-gateway`,
  `workspace-governance-control-fabric`, `workspace-governance`, and
  `security-architecture`
- Related architecture: Workspace Delivery ART #884 architecture packet v19
- Related ADR:
  `docs/decisions/adr/ADR-017-temporal-durable-workflow-runtime.md`

## Root Cause

- Immediate failure: The typed Refinement advisor profile remained inactive
  after the composition, domain contracts, and Security review landed.
- Actual root cause: Foundation work deliberately separated source registration
  from the final Platform-owned activation and live composition proof.
- Why it escaped earlier controls: It did not escape; predecessor Landing Units
  installed fail-closed source pending Security review #1012 and activation
  work item #1013.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): finalized Review Packet for ART #1013 records the merged commit.
- Guardrails added:
  - exact Refinement caller, task, schema, and local model binding activation
  - positive typed advice and suspended-profile denial before provider access
  - composition-only OOS business workflow and direct Console access denial
  - current Temporal and governed-AI operator documentation
  - no paid-provider, stage, production, tool, or autonomous mutation expansion

## Artifact And Deployment Evidence

- Build workflow run: recorded by the ART #1013 Review Packet.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Live Verification

- App health: recorded by the ART #1013 Review Packet for the exact
  `refinement-catalog` composition source head.
- Functional verification:
  - the exact Refinement caller receives typed local advice
  - immutable operator acceptance starts durable `delivery.refinement.apply`
  - repository readiness and Catalog apply/readback produce bound receipts
  - mismatched caller, profile, evidence, replay, and receipt cases fail without mutation
  - reverse teardown removes composition credentials and preserves canonical state
- Residual risk: Governance Operations Console integration remains unavailable
  until ART #1014 lands; stage, production, and paid-provider activation remain
  prohibited.

## Follow-Up Actions

- Required follow-up: ART #1014 integrates the Governance Operations Console
  through its same-origin server and OOS only.
- Owner: Governance Operations Console, OOS, Platform Engineering, and Security
  Architecture according to their existing boundaries.
