# 2026-04-22 ART Board Model Realignment

## Summary

`Workspace Delivery ART` now uses a stronger managed board set for the current
OpenProject Community Edition runtime:

- `PM² Phase Board`
- `ART Execution Kanban`
- `PI Objectives`
- `ART Risk Register`

The old `PM² Initiative Register` and `Program Increment Planning` managed
boards are no longer part of the supported board model. PM² governance now has
explicit phase lanes, PI objective visibility now operates through
committed-versus-stretch lanes per declared PI, and planning stays in the
supported read-model/report surfaces instead of a fake program-board-style
board.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery governance
  - operator boards and views
  - SAFe plus PM² operating model

## Ownership

- managed OpenProject board/query model and operator runbooks:
  `platform-engineering`
- live ART work-state truth:
  `Workspace Delivery ART`

## Root Cause

The earlier managed board set was directionally useful but not strongly aligned
to how the current one-ART delivery model is actually operated:

- `PM² Initiative Register` behaved like a list surface rather than a phase
  board
- `Program Increment Planning` implied a real SAFe planning board that the
  runtime could not actually support
- `PI Objectives` grouped only by PI version and did not surface committed
  versus stretch visibility directly in the board model

This left the UI with a weaker signal than the underlying SAFe plus PM²
contract and the supported planning read models.

## Source Changes

- changed the managed PM² board from a generic initiative register to
  `PM² Phase Board` with one lane per `PM² Phase`
- removed the managed `Program Increment Planning` board and its query family
- changed the managed `PI Objectives` board to generate committed/stretch lanes
  for each declared PI
- updated the delivery ART contract and operator runbooks so planning is
  explicitly treated as a supported read-model surface instead of a board
- kept the existing `ART Execution Kanban` and `ART Risk Register` intact

## Live-State Impact

- the active `accepted-idea-delivery` dev-integration lane now exposes the
  new managed board set live
- board redesign work is tracked and closed in the ART under:
  - `Feature #82`
  - `Task #83`
  - `Task #84`
  - `Task #85`

## Artifact And Deployment Evidence

- deployment artifact:
  - dev-integration proof in `devint-accepted-idea-delivery-mfshaf7`
- proof artifacts:
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-83-pm2-phase-board-proof.txt`
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-84-pi-objectives-board-proof.txt`
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-85-planning-board-retirement-proof.txt`
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-feature-82-board-redesign-proof.txt`

## Live Verification

- OpenProject pod syntax check:
  - `ruby -c /tmp/openproject_sync_delivery_art_views_runner.rb`
- live sync in the active devint lane:
  - `bundle exec rails runner /tmp/openproject_sync_delivery_art_views_runner.rb`
- resulting live boards:
  - `PM² Phase Board`
  - `ART Execution Kanban`
  - `PI Objectives`
  - `ART Risk Register`
- live readback:
  - `Epic #38 PM² Phase = Executing`
  - `PI Objective #59 type = Committed`
  - `PI Objective #58 type = Stretch`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- keep using planning through the supported read-model surfaces unless the
  runtime gains a real program-board-capable board type
- reassess whether the PI objectives board needs a stronger multi-PI layout if
  the one-ART model begins carrying multiple active PI versions at once
