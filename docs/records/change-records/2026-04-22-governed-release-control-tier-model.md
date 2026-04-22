# 2026-04-22 Governed Release Control Tier Model

## Summary

The workspace now has a standardized release-governance model for governed
source-to-stage-to-prod control across products, shared control-plane
components, and supporting components.

This change introduces:

- a shared release-governance tier model in `workspace-governance`
- a new platform standard for release-state objects and aggregate environment
  readiness
- explicit separation between release governance, runtime lifecycle, and simple
  version pinning

## Classification

- owner repo: `platform-engineering`
- workflow area:
  - stage governance
  - prod governance
  - release control
  - enterprise standards

## Ownership

- workspace contract model:
  `workspace-governance/contracts/release-governance.yaml`
- platform release-control standard:
  `platform-engineering/docs/standards/governed-release-control-model.md`
- workload-specific rollout:
  follows the owning product or component workstreams

## Root Cause

The workspace had the strongest governed release path only in OpenClaw.

That left the broader stage and prod model under-specified for:

- platform-integrated products such as OpenProject
- shared control-plane components such as
  `operator-orchestration-service`
- supporting components that materially affect environment readiness

As a result, a workload could look healthy in stage or prod while still being
stale or lacking explicit verification and readiness truth.

## Source Changes

- added the machine-readable tier model in
  `workspace-governance/contracts/release-governance.yaml`
- added the shared platform standard in
  `docs/standards/governed-release-control-model.md`
- updated the standards index plus the existing release, CI/CD, and runtime
  lifecycle standards to point at the new model
- clarified that readiness depends on release truth, not health alone

## Artifact And Deployment Evidence

- no live deployment artifact was produced in this standards tranche
- this change defines the governing model that later rollout tasks will apply
  to OpenProject, `operator-orchestration-service`, OpenClaw, and supporting
  components

## Live Verification

- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`

## Follow-Up Actions

- add standardized verification catalogs, readiness statuses, and evidence
  contracts
- add governed release-state model for
  `operator-orchestration-service`
- add governed release-state and verification model for OpenProject
- add supporting-component readiness contracts for shared stage and prod
  services
- add aggregate fail-closed environment readiness validation and operator
  workflow
- reconcile OpenClaw to the standardized release-control model terminology
