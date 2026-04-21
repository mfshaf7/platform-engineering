# Show Delivery Execution

## Purpose

Show the current execution tree for one delivery `Epic` through a supported
read-only operator surface.

Use this when you need to inspect:

- the current execution tree under one delivery initiative
- which items are blocked
- which items are dependency-blocked by unfinished predecessors
- which completed items still lack completion evidence
- which `ready` items still violate the structured execution contract
- who owns each item
- which `Target PI` values are present
- how work is distributed by status, type, team, iteration, PI objective type,
  and ROAM state

This avoids hunting manually through multiple OpenProject UI screens when the
question is operational visibility rather than editing.

Use [show-delivery-active-front.md](show-delivery-active-front.md) first for a
routine startup read. Use this deeper surface when the active `Epic` is
already known and you need the full execution details.

## Command

Run from `platform-engineering/`:

```bash
make openproject-show-delivery-execution \
  TARGET_EPIC_ID=38
```

Optional fields:

- `INCLUDE_DONE=true|false`
- `INCLUDE_INACTIVE=true|false`
- `INCLUDE_PARKED=true|false` as a backward-compatible alias

Examples:

```bash
make openproject-show-delivery-execution \
  TARGET_EPIC_ID=38 \
  INCLUDE_DONE=false \
  INCLUDE_INACTIVE=false
```

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-show-delivery-execution \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38
```

## Expected Outcome

The command prints JSON with:

- the top-level `Epic`
- summary counts by status, type, PI, and assignee
- summary counts by delivery team, iteration, PI objective type, and ROAM state
- summary counts for dependency links and unresolved dependencies
- a `parked_items` list when parked descendants exist
- a `retired_items` list when retired descendants exist
- a list of blocked items with blocker details when present
- a list of `ready` items missing required execution fields
- a list of `done` items missing `Completion Summary`, `Changed Surfaces`, or
  `Test Result Evidence`, or `Validation Evidence`
- PI-objective business-value rollups and ART risk counts
- `dependency_relations` plus `unresolved_dependency_relations`
- the recursive execution tree under the target epic

Each item summary also reports attachment visibility through:

- `attachment_count`
- `attachment_filenames`

Default visibility:

- `INCLUDE_DONE=true` shows completed descendants
- `INCLUDE_INACTIVE=false` hides inactive descendants (`parked` and `retired`)
  from the tree by default while still reporting them in `parked_items` and
  `retired_items`

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target `Epic`
- compare the summary output with the visible work-package tree
- confirm blocked items and PI placement match the current UI state
- confirm dependency links and unresolved predecessors match the relations shown on the affected work items

## Related References

- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [show-delivery-active-front.md](show-delivery-active-front.md)
- [show-delivery-planning.md](show-delivery-planning.md)
- [show-pi-objectives.md](show-pi-objectives.md)
- [start-delivery-execution.md](start-delivery-execution.md)
- [move-delivery-work-item.md](move-delivery-work-item.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [manage-delivery-dependency.md](manage-delivery-dependency.md)
- [manage-delivery-blocker.md](manage-delivery-blocker.md)
- [manage-delivery-parking.md](manage-delivery-parking.md)
- [check-delivery-closeout-readiness.md](check-delivery-closeout-readiness.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
