# 2026-04-21 Delivery Retired Status Model

## Summary

`Workspace Delivery ART` now distinguishes deferred inactive work from terminal
inactive work:

- `parked` = deferred and potentially resumable
- `retired` = terminal and not expected to return
- `superseded`, `duplicate`, `invalid`, `absorbed`, and `cancelled` are
  retirement reasons, not primary statuses

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery execution
  - inactive-scope governance

## Ownership

- OpenProject product model, status configuration, read models, and operator
  runbooks: `platform-engineering`
- ART work-state truth: `Workspace Delivery ART`

## Root Cause

The earlier delivery model overloaded `parked` for both deferred work and
terminal duplicate or mistaken work. That was audit-safe but operationally
misleading because it made superseded items look as if they might return later.

## Source Changes

- added delivery status `retired`
- added custom field `Retirement Reason`
- updated inactive-scope handling so:
  - `parked` remains deferred-only
  - `retired` is the terminal inactive state
  - `superseded` becomes a retirement reason rather than a status
- updated planning, execution, initiative, quality, and closeout read models so
  retired items do not appear in normal open-scope views
- updated parking and plan-reconciliation workflows to write the right inactive
  semantics

## Live-State Impact

- the active devint delivery project now carries:
  - status `retired`
  - custom field `Retirement Reason`
- duplicated root-level items `#69` and `#73` were migrated from `parked` to:
  - `status = retired`
  - `Retirement Reason = superseded`

## Artifact And Deployment Evidence

- deployment artifact:
  - live devint OpenProject reconfiguration in
    `devint-accepted-idea-delivery-mfshaf7`

## Live Verification

- direct OpenProject runner proof confirmed:
  - delivery project contains status `retired`
  - delivery project contains custom field `Retirement Reason`
- active initiative and execution reads with inactive hidden now report:
  - `retired_descendant_total: 0`
  - `retired_count: 0`
  - `inactive_count: 0`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- keep future duplicate or mistaken work terminal through `retired`, not
  `parked`
- reserve `parked` only for genuinely deferred work that may return later
