# 2026-04-30 OpenProject ART Backlog Narrative Quality Boundary

## Summary

Relaxed the delivery ART quality checker so lightweight planned backlog
descriptions are reported as advisory `polish` instead of hard failures.
Executable, PI-committed, blocked, and done work still keeps the stronger
narrative-quality gate.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery ART quality
  - backlog decomposition
  - narrative quality gates

## Ownership

- Platform OpenProject ART quality checker:
  `platform-engineering`
- Broker-side ART mutation and completion enforcement:
  `operator-orchestration-service`
- Related ART records:
  - `#420` Workspace Governance Control Fabric initiative
  - `#467` relax ART planning controls for non-executable backlog decomposition

## Root Cause

The ART contract already treated non-done narrative findings as advisory, but
the quality checker still emitted `description_does_not_start_with_heading` as a
hard issue for every planned backlog child. That made future decomposition look
invalid even when the item was intentionally non-executable.

## Source Changes

- updated `products/openproject/scripts/openproject_check_delivery_art_quality.py`
  to classify loose planned backlog descriptions as backlog `polish`
- compacted default quality output by suppressing full backlog-polish detail
  unless `INCLUDE_POLISH_DETAILS=true`
- kept hard failures for loose descriptions once work becomes executable,
  PI-committed, blocked, or done
- extended
  `products/openproject/scripts/test_openproject_check_delivery_art_quality.py`
  with regression coverage for both relaxed and hard-fail paths
- updated `products/openproject/delivery-art-contract.md` and
  `products/openproject/runbooks/check-delivery-art-quality.md`

## Artifact And Deployment Evidence

- no runtime artifact or governed deployment changed
- the change affects the platform-owned ART quality script and operator docs

## Live Verification

- `python3 -m unittest products.openproject.scripts.test_openproject_check_delivery_art_quality`
- `python3 scripts/validate_operational_docs.py`
- `make openproject-check-delivery-art-quality OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 TARGET_EPIC_ID=420`
  - `issue_count: 0`
  - `suppressed_polish_finding_count: 72`
  - one remaining `discussion-required` next-up narrative finding for `#422`

## Follow-Up Actions

- keep executable work narratives strong before starting or completing those
  items
- continue using backlog polish findings as cleanup guidance, not as a planning
  blocker
