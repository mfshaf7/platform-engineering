# 2026-05-05 OpenProject ART PI lifecycle contract

## Summary

- Date: 2026-05-05
- Short title: OpenProject ART PI lifecycle contract
- Environment: source contract and local quality tooling
- Severity: medium

## Classification

- Type:
  - workflow contract hardening
  - quality gate hardening
- User-facing impact: operators now have explicit rules for when to create or
  select a new PI and when a committed item has a stale iteration label.

## Ownership

- Owning repo or layer: `platform-engineering/products/openproject`
- Related repos: `operator-orchestration-service`,
  `workspace-governance-control-fabric`, `workspace-governance`
- Related ART slice: `#613` PI Objective, `#614` Feature, `#615` platform
  owner story, `#616` broker owner story, `#617` WGCF owner story, and `#618`
  workspace-governance owner story under reopened `#498`.
- Related ADR: None.

## Root Cause

- Immediate failure: the ART contract did not state whether a large item count
  alone should force a new PI.
- Actual root cause: PI placement rules existed, but PI lifecycle and
  iteration-to-Target-PI alignment were not first-class machine-readable
  controls.
- Why it escaped earlier controls: existing quality checks focused on `Target
  PI`, roadmap projection, PI Objectives, and leaf-front shape, not whether the
  committed iteration label belonged to the same PI.

## Source Changes

- Repo: `platform-engineering`
- Commit(s): pending PR in this landing unit
- Guardrail added:
  - test
  - validator
  - runbook
  - ADR: None

## Artifact And Deployment Evidence

- Build workflow run: None.
- Published image tag: None.
- Published digest: None.
- Recorded prod revision: None.
- Argo application revision: None.

## Host Or Runtime Recovery

None.

## Live Verification

- App health: not applicable to source-only contract hardening.
- Deployed image: None.
- Pod: None.
- Functional verification:
  - PASS: `python3 -m unittest products.openproject.scripts.test_openproject_check_delivery_art_quality`
    ran 34 tests successfully.
  - PASS: `python3 scripts/validate_repo_structure.py --repo-root .`
    confirmed platform repo structure validity.
  - PASS: WGCF delivery-art scoped receipt
    `control-receipt:29d76942ee23c573f8f096c5` selected
    `openproject-quality-check` and completed within the 120-second hard-gate
    budget after ART projection sync and #498 reopening.
- Residual risk: existing historical done items are not backfilled unless a
  future audit chooses to normalize them.

## Follow-Up

- Required follow-up: None.
- Optional hardening: add a future PI calendar registry only when we need
  date-based capacity and cutoff enforcement.
- Owner: Platform Engineering
