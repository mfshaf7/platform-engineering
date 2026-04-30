# 2026-04-30 ART Version Projection Workflow Step

## Summary

Updated the OpenProject delivery ART planning workflow and runbooks so roadmap
`version` projection sync is a required post-mutation workflow step whenever an
ART change can move work between roadmap buckets.

## Classification

- area: OpenProject delivery ART
- type: operator workflow doctrine
- runtime impact: documentation and workflow metadata only

## Ownership

- owner repo: `platform-engineering`
- related product: `openproject`
- related ART slice:
  - `#420` `Build Workspace Governance Control Fabric foundation for scalable validation, evidence, and admission`
  - `#426` `Enabler: Define the control-fabric architecture, operating model, and threat boundary`

## Root Cause

Projection sync was documented as the repair path for drift, but the planning
workflow did not make it explicit enough that sync is also the normal follow-up
after any projection-affecting ART mutation. During #426 activation, the broker
committed work correctly, but the roadmap `version` projection required platform
sync before quality passed.

## Source Changes

- updated canonical planning workflow metadata:
  - `products/openproject/delivery-art-planning-workflow.json`
- updated operator runbooks:
  - `products/openproject/README.md`
  - `products/openproject/delivery-art-contract.md`
  - `products/openproject/runbooks/plan-delivery-art.md`
  - `products/openproject/runbooks/sync-delivery-art-views.md`
  - `products/openproject/runbooks/check-delivery-art-quality.md`
- updated the governance-doc validator so the change-record template itself
  must keep the same closure headings as real change records:
  - `scripts/validate_governance_docs.py`

## Artifact And Deployment Evidence

- documentation, workflow metadata, and governance-template guard change only
- no stage or production runtime deployment in this slice

## Live Verification

- platform sync reconciled four #426-#429 roadmap projections into `PI-2026-03`
- scoped ART quality for #420 passed afterward with `issue_count=0` and
  `roadmap_projection_drift_count=0`

## Follow-Up

- keep the broker planning-workflow mirror and workspace ART operator skill in
  sync with this canonical platform workflow rule
