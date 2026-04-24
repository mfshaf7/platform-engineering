# 2026-04-25 Delivery ART Roadmap Projection Truth

## Summary

The `Workspace Delivery ART` roadmap projection now stays honest to the whole
ART instead of only the subset that already carried an OpenProject `version`.
`Target PI` remains the canonical writable planning field, while the managed
OpenProject view sync now projects:

- PI-assigned work into the matching PI `version`
- work without `Target PI` into the derived backlog bucket
  `Not yet committed to a PI`

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery execution
  - PI planning views
  - roadmap compatibility

## Ownership

- canonical OpenProject roadmap projection and ART quality policy:
  `platform-engineering`
- broker planning field contract and operator execution surface:
  `operator-orchestration-service`

## Root Cause

The managed delivery-art view sync was only projecting work that already had
`Target PI` into matching OpenProject versions. That left most of the ART with
`version = null`, so the OpenProject roadmap page silently under-reported the
work even when the canonical `Target PI` data was present. It also dropped ART
work with blank `Target PI` entirely instead of showing that it was still not
committed to any PI.

## Source Changes

- updated the delivery-art view sync runner so PI-assigned work projects into
  matching versions and unassigned work projects into the derived roadmap
  bucket `Not yet committed to a PI`
- excluded the derived backlog bucket from PI-objective boards so PI lanes stay
  PI-shaped
- strengthened the ART quality check so it fails when `Target PI` and roadmap
  `version` diverge or when unassigned work is missing the derived backlog
  bucket
- strengthened the ART quality check further so active non-`Epic` work cannot
  remain in `ready`, `in-progress`, or `blocked` without canonical `Target PI`
- updated the OpenProject delivery contract and runbooks to describe the whole
  projection model explicitly

## Artifact And Deployment Evidence

- active devint `workspace-delivery-art` roadmap projection is now aligned to
  live ART truth
- PI-assigned work is visible under its real PI version
- unassigned ART work can now be surfaced on the roadmap through the derived
  backlog bucket instead of disappearing from the page

## Live Verification

- active devint view sync now reports the full derived version set:
  - `Not yet committed to a PI`
  - `PI-2026-02`
  - `PI-2026-03`
- post-sync live cross-tab proves:
  - `PI-2026-02 -> PI-2026-02 = 137`
  - `PI-2026-03 -> PI-2026-03 = 7`
  - `_none_ -> Not yet committed to a PI = 87`
- live roadmap-compatible version/status distribution now shows:
  - `Not yet committed to a PI`: `87` work packages
  - `PI-2026-02`: `137` work packages
  - `PI-2026-03`: `7` work packages
- `python3 -m unittest products/openproject/scripts/test_openproject_check_delivery_art_quality.py`
- `python3 scripts/validate_repo_structure.py --repo-root .`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`

## Follow-Up

- keep the persistent `accepted-idea-delivery` lane running the automated view
  reconciler so roadmap drift heals without a manual sync run
- continue treating `Target PI` as canonical and `version` as a derived
  compatibility projection only
