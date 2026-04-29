# 2026-04-30 OpenProject WGCF Identity And Backlog Leaf Planning

## Summary

Added the Workspace Governance Control Fabric delivery ART identity and aligned
the platform OpenProject ART planning quality contract with the broker-side rule
that backlog `Feature` records may keep `new` planned `User story` children as
non-executable future decomposition.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery ART identity provisioning
  - delivery ART planning quality
  - PI planning and backlog decomposition

## Ownership

- OpenProject product integration and delivery identity provisioning:
  `platform-engineering`
- Broker create, move, and planning-state enforcement:
  `operator-orchestration-service`
- Related ART records:
  - `#420` Workspace Governance Control Fabric initiative
  - `#424` provision control-fabric delivery ART identity
  - `#467` relax backlog leaf planning controls

## Root Cause

The delivery ART identity list did not yet include
`workspace-governance-control-fabric`, so the new repo could not be selected as
an assignee through the platform-owned identity model. At the same time, the
platform quality mirror still treated all open `User story` records without
`Target PI` as invalid, which blocked the legitimate `#420` planning shape
where future-phase leaf records must remain visible but non-executable.

## Source Changes

- added `workspace-governance-control-fabric` to
  `products/openproject/delivery-art-identities.json`
- updated
  `products/openproject/runbooks/provision-delivery-art-identities.md` with the
  new delivery ART identity
- updated `products/openproject/delivery-art-planning-workflow.json`,
  `products/openproject/delivery-art-contract.md`, and
  `products/openproject/runbooks/plan-delivery-art.md` to distinguish planned
  backlog `User story` children from executable story scope
- updated `products/openproject/scripts/openproject_check_delivery_art_quality.py`
  to allow non-executable planned backlog stories while still reporting
  executable child scope under backlog Features
- extended
  `products/openproject/scripts/test_openproject_check_delivery_art_quality.py`
  with regression coverage for the allowed and rejected shapes

## Live-State Impact

- active `accepted-idea-delivery` dev-integration lane now has a live
  OpenProject user assignable as `Workspace Governance Control Fabric`
- no governed stage or prod deployment changed

## Artifact And Deployment Evidence

- identity provisioning used the platform-owned delivery ART identity contract
  path with `OPENPROJECT_DELIVERY_ART_IDENTITY_CONTRACT`
- live assignable proof:
  - `npm run art -- assignees --json`
  - principal id `12`
  - login `Workspace Governance Control Fabric`
- broker source prerequisite:
  - `operator-orchestration-service#82`
  - source SHA `305a540a473b2b9d67dd93c035e522b4b7f5ae05`
  - image digest
    `sha256:fc935f37a4e9dd0ddb6b8baf83e740541136fe6b81ac646de2939eee9d14a23b`

## Live Verification

- `python3 -m unittest products.openproject.scripts.test_openproject_check_delivery_art_quality`
- `python3 scripts/validate_repo_structure.py`
- `python3 scripts/validate_governance_docs.py`
- `python3 scripts/validate_operational_docs.py`
- `python3 -m json.tool products/openproject/delivery-art-planning-workflow.json`
- `python3 -m json.tool products/openproject/delivery-art-identities.json`
- `git diff --check`

## Follow-Up

- refresh the active dev-integration broker runtime to the merged OOS image
- use the fixed broker path to assign/preserve the `#420` future-phase records
  without retiring them or adding fake PI commitment
