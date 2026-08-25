# Governed Work Design Profile Activation

## Summary

- Date: 2026-08-25
- Short title: Activate bounded Work Design advice in dev-integration
- Environment: local `dev-integration`
- Severity: Medium

## Classification

- Type: platform governance activation
- User-facing impact: Enables the reviewed OOS Work Design caller to request
  bounded model advice without enabling Console consumption or canonical writes.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `operator-orchestration-service`, `context-governance-gateway`,
  `security-architecture`
- Related architecture: Workspace Delivery ART #884 architecture packet v9
- Related ADR:
  `docs/decisions/adr/ADR-021-multi-profile-governed-ai-gateway.md`

## Root Cause

- Immediate failure: The typed Work Design profile existed but its profile,
  binding, caller lifecycle, and access-plane activation remained inactive.
- Actual root cause: Foundation work intentionally separated registration from
  live activation so exact integration and Security evidence could land first.
- Why it escaped earlier controls: It did not escape; ART #992 deliberately
  installed a fail-closed inactive profile pending #993 and #994.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): finalized Review Packet for ART #995 records the merged commit.
- Guardrails added:
  - Work Design-only dev-integration activation under Security review #994
  - typed positive and mismatched caller/profile/task negative runtime probes
  - per-profile readiness and selected-binding audit evidence
  - independent suspension proof that preserves intake availability
  - no Console, paid-provider, stage, prod, tool, or canonical-write expansion
  - shared local binding reconciled from Ollama `0.32.14` to the observed
    `0.32.15` patch runtime while retaining the reviewed model digest

## Artifact And Deployment Evidence

- Build workflow run: recorded by the ART #995 Review Packet.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Live Verification

- App health: local-k3s gateway, consumer probe, and provider sentinel ready.
- Functional verification:
  - exact Work Design caller/task/schema invocation succeeds through the gateway
  - mismatched Work Design caller/profile/task fails before provider access
  - intake compatibility invocation remains successful
  - audit ledger retains selected binding and CGG packet references
  - ordinary gateway restart retains prior audit events
  - direct provider and direct Ollama paths remain denied to the consumer
- Residual risk: Console integration remains unavailable until ART #996 lands;
  stage, prod, and paid-provider activation remain prohibited.

## Follow-Up Actions

- Required follow-up: ART #996 integrates the Governance Operations Console
  through its same-origin server and OOS; the browser must not call CGG, the
  gateway, a provider, or OpenProject directly.
- Owner: Governance Operations Console, OOS, Platform Engineering, CGG, and
  Security Architecture according to their existing boundaries.
