# Governed AI Access Plane Source Contract

## Summary

- Date: 2026-04-29
- Short title: Governed AI access-plane source contract
- Environment: platform source control
- Severity: Medium

## Classification

- Type: platform governance contract
- User-facing impact: Establishes the platform-owned source contract for the
  governed AI invocation boundary, provider credential custody, caller identity,
  audit metadata, and devint egress enforcement before any consumer activation.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `security-architecture`, `workspace-governance`
- Related ADR: `docs/decisions/adr/ADR-012-governed-ai-access-plane-and-model-profiles.md`

## Root Cause

- Immediate failure: Delivery `#353/#354/#355` needed the shared access-plane
  source contract before workspace consumers could safely implement governed
  intake assist.
- Actual root cause: The runtime-assist activation contract existed, but the
  platform access-plane contract and devint egress enforcement contract were not
  yet separated as reviewable source truth.
- Why it escaped earlier controls: Earlier slices intentionally stopped at the
  profile and runtime-assist activation boundary before implementing the access
  plane source contract.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): pending PR merge
- Guardrail added: validator
- Guardrail added: standard
- Guardrail added: source contract

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
- Residual risk: Live profile activation remains blocked until the governed AI
  gateway, audit sink, caller identity proof, provider-egress block, and rollback
  evidence exist in devint.

## Follow-Up

- Required follow-up: Implement the actual devint runtime gateway and prove the
  egress policy before changing any profile status to `active`.
- Optional hardening: Add runtime smoke checks that prove both positive gateway
  reachability and negative direct-provider reachability.
- Owner: Platform Engineering
