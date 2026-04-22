# 2026-04-22 Release Verification And Readiness Contract Model

## Summary

The governed release-control model now has a shared verification and readiness
contract instead of leaving those semantics mostly implicit inside OpenClaw's
product-specific files.

This tranche standardizes:

- verification status vocabulary
- readiness status vocabulary
- shared check-result statuses
- verification catalog expectations
- evidence-reference expectations for verification and post-promotion proof

## Classification

- owner repo: `platform-engineering`
- workflow area:
  - stage governance
  - prod governance
  - release verification
  - evidence contracts

## Ownership

- machine-readable verification and readiness contract:
  `workspace-governance/contracts/release-verification.yaml`
- platform standard and operator interpretation:
  `platform-engineering/docs/standards/governed-release-control-model.md`
- workload-specific rollout:
  still belongs to the owning product or component workstreams

## Root Cause

The previous tranche defined release-governance tiers and release-state object
types, but it did not yet standardize how verification catalogs, readiness
statuses, and evidence references should behave across the workspace.

That left the strongest semantics inside OpenClaw-specific implementation
details and made it too easy for future workloads to drift into different or
weaker status and evidence models.

## Source Changes

- added the shared verification and readiness contract in
  `workspace-governance/contracts/release-verification.yaml`
- added the `release-governance` change class and corresponding evidence
  obligations in `workspace-governance`
- extended the governed release-control standard with:
  - verification status vocabulary
  - readiness status vocabulary
  - check-result status vocabulary
  - verification catalog rules
  - evidence-reference rules

## Artifact And Deployment Evidence

- no live deployment artifact was produced in this standards tranche
- this change defines the shared verification and readiness contract that later
  workload rollout tasks must adopt

## Live Verification

- `python3 scripts/validate_repo_structure.py --repo-root .`
- `python3 scripts/validate_contracts.py --repo-root .`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `python3 scripts/render_register_views.py --repo-root .`
- `python3 scripts/validate_security_evidence.py --repo-root .`

## Follow-Up Actions

- reconcile OpenClaw's stage catalog naming to the standardized contract
- adopt the shared verification and readiness vocabulary in
  `operator-orchestration-service`
- adopt the shared verification and readiness vocabulary in OpenProject
- define supporting-component support-readiness records and checks
- add aggregate fail-closed environment readiness validation that consumes the
  standardized verification objects
