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

# Governed AI Gateway Dev-Integration Runtime

## Summary

- Date: 2026-05-06
- Short title: Governed AI gateway dev-integration runtime
- Environment: dev-integration
- Severity: Medium

## Classification

- Type: platform governance runtime
- User-facing impact: Adds the first platform-owned dev-integration runtime
  profile for the governed AI access-plane gateway, including caller identity,
  provider custody, audit emission, and provider-egress proof surfaces.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `workspace-governance`, `security-architecture`
- Related ADR: `docs/decisions/adr/ADR-012-governed-ai-access-plane-and-model-profiles.md`

## Root Cause

- Immediate failure: Delivery `#411/#412/#413` could not remove the governed
  intake-assist activation blocker with source contracts alone.
- Actual root cause: The platform had profile and access-plane contracts, but
  no runnable dev-integration gateway boundary to prove caller identity,
  provider custody, audit emission, or consumer egress controls.
- Why it escaped earlier controls: Earlier `#251` slices intentionally stopped
  at source-defined policy and kept the model profile suspended until runtime
  proof and security review existed.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): pending PR merge
- Guardrail added:
  - dev-integration profile
  - component docs
  - validator
  - security-evidenced change record

## Artifact And Deployment Evidence

- Build workflow run: Not applicable; no image build in this slice.
- Published image tag: Not applicable.
- Published digest: Not applicable.
- Recorded prod revision: Not applicable.
- Argo application revision: Not applicable.

## Host Or Runtime Recovery

None. This is a local-k3s dev-integration runtime profile and does not alter
stage or prod.

## Live Verification

- App health: `make devint-smoke PROFILE=governed-ai-gateway` passed in local
  dev-integration.
- Deployed image: dev-integration runtime uses `python:3.12-slim`
- Pod: `governed-ai-gateway`, `governed-ai-consumer-probe`, and
  `direct-provider-sentinel` rolled out in the active local profile namespaces.
- Functional verification:
  - `python3 scripts/validate_ai_model_profiles.py --repo-root .`
  - `python3 scripts/validate_repo_structure.py --repo-root .`
  - `make devint-up PROFILE=governed-ai-gateway`
  - `make devint-smoke PROFILE=governed-ai-gateway`
  - `make devint-promote-check PROFILE=governed-ai-gateway`
- Smoke result: gateway reachable from consumer, direct-provider sentinel not
  reachable from consumer, audit event emitted, caller identity captured,
  provider Secret available only in gateway custody, provider token not
  projected, and profile status remains `suspended`.
- Residual risk: `intake-classifier-v1` remains suspended until workspace
  live-consumption activation and upstream model/provider selection gates pass.

## Follow-Up

- Required follow-up: Land security delta review and workspace profile
  activation before treating governed intake-assist as live.
- Optional hardening: Replace the dev-integration provider sentinel with a
  real provider adapter only after model/provider selection is approved.
- Owner: Platform Engineering / Security Architecture / Workspace Governance
