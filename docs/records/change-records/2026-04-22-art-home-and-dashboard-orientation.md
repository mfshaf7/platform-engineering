# 2026-04-22 ART Home And Dashboard Orientation

## Summary

`Workspace Delivery ART` now has a generated project overview and a managed
`ART Dashboard` board so the project landing surfaces explain the operating
model and show the highest-signal live execution state at a glance.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery governance
  - operator orientation
  - managed board and overview surfaces

## Ownership

- OpenProject delivery-art model, generated project home, managed board/query
  sync, and operator runbooks: `platform-engineering`
- live ART work-state truth: `Workspace Delivery ART`

## Root Cause

The existing delivery-art home was a one-line description that did not explain
how to use the ART or which surfaces mattered. The project also lacked a
summary board that brought together active initiatives, committed objectives,
current execution, owned risks, and deferred open work.

That left the project landing experience dull and low-signal even though the
underlying ART model had already become disciplined and information-rich.

## Source Changes

- added shared helper
  `products/openproject/scripts/openproject_delivery_art_home_support.rb`
  for generated ART project-home content
- updated `openproject_configure_delivery_art_runner.rb` to seed the richer
  ART overview from the shared helper
- updated `openproject_sync_delivery_art_views_runner.rb` to refresh the
  overview text and create the managed `ART Dashboard` board
- updated the configure and sync shell entrypoints so the shared home helper is
  copied into the OpenProject pod alongside the runner scripts
- updated the delivery-art contract and runbooks to treat the overview and
  `ART Dashboard` as part of the supported ART operator surface

## Live-State Impact

- the active `accepted-idea-delivery` dev-integration lane now shows:
  - a generated ART overview explaining purpose, boards, status meanings, and
    truth split
  - managed board `ART Dashboard`
  - managed dashboard widgets for:
    - active initiatives
    - committed objectives
    - active execution
    - blocked execution
    - owned risks
    - parked work

## Artifact And Deployment Evidence

- deployment artifact:
  - live devint OpenProject refresh in
    `devint-accepted-idea-delivery-mfshaf7`
- proof artifact:
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-86-art-home-and-dashboard-proof.txt`

## Live Verification

- live sync created board `ART Dashboard` with `widget_count = 6`
- live project overview now includes:
  - `Purpose`
  - `Use These Surfaces`
  - `Operating Model`
  - `Status Meaning`
  - `Delivery Truth`
- dashboard widget readback now returns:
  - active initiatives -> `#38`
  - committed objectives -> `#59`
  - active execution -> `#61`, `#76`, `#80`, `#86`
  - blocked execution -> none
  - owned risks -> `#60`
  - parked work -> `#77`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- keep the ART overview generated from the shared helper instead of editing the
  project description manually in the UI
- keep the `ART Dashboard` managed through the sync path so future model
  changes refresh the operator landing surface automatically
