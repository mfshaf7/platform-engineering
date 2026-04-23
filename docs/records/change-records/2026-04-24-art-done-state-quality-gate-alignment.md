# 2026-04-24 ART Done-State Quality-Gate Alignment

## Summary

`platform-engineering` now treats broker-reported done-state narrative drift as
a hard `Workspace Delivery ART` quality failure instead of leaving it in the
advisory narrative lane.

## Classification

- owner surface:
  - `products/openproject/scripts/openproject_check_delivery_art_quality.py`
- related contract and operator docs:
  - `products/openproject/delivery-art-contract.md`
  - `products/openproject/runbooks/check-delivery-art-quality.md`

## Ownership

- broker-signal consumption and ART quality-gate behavior:
  `platform-engineering`
- broker-side done-state narrative enforcement:
  `operator-orchestration-service`
- ART skill and improvement-candidate closure:
  `workspace-governance`

## Root Cause

The ART quality gate already failed on weak completion evidence, but it still
treated done-state narrative quality as either generic structure drift or
advisory narrative weakness. That left a mismatch with the stronger broker-side
closeout contract and made it too easy to assume a rough done record was only a
polish issue.

## Source Changes

- added broker-signal handling for:
  - `done_narrative_contract_applicable`
  - `done_narrative_contract_satisfied`
  - `done_narrative_contract_issues`
- added a local regression test seam in
  [products/openproject/scripts/test_openproject_check_delivery_art_quality.py](../../../products/openproject/scripts/test_openproject_check_delivery_art_quality.py)
- updated the operator and contract docs to distinguish advisory active-work
  narrative findings from hard done-state closeout failures

## Artifact And Deployment Evidence

- artifact:
  - ART quality checker support for `done_narrative_contract_*`
  - local regression test seam for the quality checker
- proof:
  - platform docs and contract text now describe done-state narrative drift as
    a structural failure

## Live Verification

- `python3 -m unittest products/openproject/scripts/test_openproject_check_delivery_art_quality.py`
- `python3 scripts/validate_repo_structure.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_governance_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `python3 scripts/validate_operational_docs.py --repo-root /home/mfshaf7/projects/platform-engineering`
- `git diff --check`

## Follow-Up

- use the updated checker once the matching broker branch is deployed or merged
- keep the broker and platform issue vocabulary aligned so future ART quality
  drift cannot split into two standards again
