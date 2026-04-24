# 2026-04-24 Devint Persistent Smoke Isolation

## Summary

Separated persistent dev-integration working lanes from mutating smoke so the
shared `accepted-idea-delivery` ART lane no longer acts as the pollution target
for test artifacts.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `operator-orchestration-service`
  - `workspace-governance`
- trust-boundary areas:
  - runtime
  - delivery

## Ownership

- shared devint runner enforcement and operator runbook updates:
  `platform-engineering`
- profile-local smoke split and companion profile implementation:
  `operator-orchestration-service`
- lifecycle contract, profile registry truth, and skill guidance:
  `workspace-governance`

## Root Cause

The active `accepted-idea-delivery` profile is the only durable local ART lane
for the current delivery flow. Its original smoke command created new proposal
and delivery records inside that same persistent working state, which leaked
test scope into the best current operator lane and even left smoke artifacts in
Workspace Delivery ART.

## Source Changes

- added a workspace-level contract that persistent profiles must keep shared
  `devint-smoke` read-only
- enforced that rule in the shared `platform-engineering` devint runner
- updated the primary operator runbook and lane standard so persistent profiles
  are described as working lanes rather than mutation-smoke targets
- accepted the new disposable `accepted-idea-delivery-mutation-smoke`
  companion profile for consume/backlink smoke

## Artifact And Deployment Evidence

- no governed artifact or Argo revision is produced by this lane
- the governed operator surface for devint profile usage remains:
  `docs/runbooks/dev-integration-profiles.md`
- the companion-profile acceptance ref is recorded here so the workspace
  profile registry can point to one concrete platform-owned change record

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root .`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `python3 -m py_compile scripts/dev_integration.py`
- `git diff --check`

## Follow-Up

- keep the shared runner and devint runbook aligned if more persistent profiles
  are admitted later
- do not treat the persistent workbench as the place for mutating smoke again;
  use or admit disposable companion profiles instead
