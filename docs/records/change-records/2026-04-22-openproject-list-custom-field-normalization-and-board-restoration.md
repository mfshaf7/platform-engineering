# 2026-04-22 OpenProject List Custom-Field Normalization And Board Restoration

## Summary

The managed `Workspace Delivery ART` boards were present but effectively empty
for PM², PI objective, and ROAM lanes because list custom fields were being
stored with display labels instead of the OpenProject custom-option ids that
the managed query filters actually match.

This fix adds one shared list-field support layer, normalizes existing ART
list-field storage in the active project, and restores the managed board data
through the official delivery-art sync path.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery governance
  - managed ART boards
  - list custom-field storage

## Ownership

- OpenProject delivery-art model, managed board/query sync, and operator
  runbooks: `platform-engineering`
- live ART work-state truth: `Workspace Delivery ART`

## Root Cause

The earlier board redesign changed the managed query families correctly, but
the surrounding delivery-art runners were still writing OpenProject list custom
fields using rendered labels like `Executing`, `Committed`, and `Owned`.

OpenProject stores those list fields as custom-option ids in
`custom_values.value`, and the managed board queries filter on those option
ids. That left the data readable in some ad hoc surfaces while the board lanes
and query filters silently missed the records.

## Source Changes

- added shared helper
  `products/openproject/scripts/openproject_delivery_art_custom_field_support.rb`
  for:
  - list-field write normalization
  - rendered list-field reads
  - live ART list-field storage normalization
- updated delivery-art runners so list fields are written through that helper
  instead of storing rendered labels directly
- updated initiative, execution, planning, closeout, and PI objective read
  surfaces to render list custom fields from stored option ids
- updated the managed ART sync path so it normalizes existing list-field
  storage before recreating queries and boards
- updated the sync-delivery-art-views operator runbook to make that storage
  normalization explicit

## Live-State Impact

- the active `accepted-idea-delivery` dev-integration lane now has corrected
  list-field storage for the ART project
- the managed boards again show live records for:
  - `PM² Phase Board`
  - `PI Objectives`
  - `ART Risk Register`
- the `ART Execution Kanban` continues to show deferred open work through the
  `parked` lane

## Artifact And Deployment Evidence

- deployment artifact:
  - live devint OpenProject reconfiguration in
    `devint-accepted-idea-delivery-mfshaf7`
- proof artifacts:
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-83-pm2-phase-board-proof.txt`
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-84-pi-objectives-board-proof.txt`
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-feature-82-board-redesign-proof.txt`

## Live Verification

- live delivery-art sync normalized existing list-field storage:
  - `normalized_list_custom_values.count = 14`
  - fields normalized:
    - `NFR Category`
    - `PI Objective Type`
    - `PM² Phase`
    - `Parking Decision`
    - `ROAM State`
    - `Retirement Reason`
- official initiative readback now reports:
  - `Epic #38 PM² Phase = Executing`
  - `PI objectives by type = {Committed: 1, Stretch: 1}`
  - `ROAM state summary = {Owned: 1}`
- managed board query readback under a real OpenProject user context now
  returns:
  - `PM² Phase / Executing` -> `#38`
  - `PI Objectives / PI-2026-02 / committed` -> `#59`
  - `PI Objectives / PI-2026-02 / stretch` -> `#58`
  - `ART Risks / Owned` -> `#60`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- keep writing ART list fields through the shared helper so query/board filters
  continue to match the live data model
- treat board-lane emptiness as a storage-contract signal first, not just a UI
  sync problem
