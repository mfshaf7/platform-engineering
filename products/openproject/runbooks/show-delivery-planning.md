# Show Delivery Planning

## Purpose

Show the current team-and-iteration planning summary for one delivery `Epic`
through a supported read-only operator surface.

Use this when you need to inspect:

- how work is distributed by `Delivery Team`
- how work is distributed by `Iteration`
- the team-by-iteration workload matrix
- current estimated and remaining work
- which `ready` items still violate the structured execution contract

This is the planning-oriented view for one initiative. Use
[show-delivery-execution.md](show-delivery-execution.md) when you need the full
recursive tree and dependency detail.

## Command

Run from `platform-engineering/`:

```bash
make openproject-show-delivery-planning \
  TARGET_EPIC_ID=38
```

Optional fields:

- `INCLUDE_DONE=true|false`
- `INCLUDE_INACTIVE=true|false`
- `INCLUDE_PARKED=true|false` as a backward-compatible alias

Example:

```bash
make openproject-show-delivery-planning \
  TARGET_EPIC_ID=38 \
  INCLUDE_DONE=false \
  INCLUDE_INACTIVE=false
```

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-show-delivery-planning \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38
```

## Expected Outcome

The command prints JSON with:

- the top-level `Epic`
- summary counts by status, type, PI, and assignee
- total estimated work, total remaining work, and average completion
- `ready_without_contract_count`
- rollups by `Delivery Team`
- rollups by `Iteration`
- a `team_iteration_matrix` for the current initiative

Default visibility:

- `INCLUDE_DONE=false` hides completed descendants
- `INCLUDE_INACTIVE=false` hides inactive descendants (`parked` and `retired`)

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target initiative
- compare `Delivery Team`, `Iteration`, PI, and execution status values with the
  summary output
- confirm the workload split matches the current active plan

## Related References

- [show-delivery-execution.md](show-delivery-execution.md)
- [show-pi-objectives.md](show-pi-objectives.md)
- [bulk-update-delivery-work-items.md](bulk-update-delivery-work-items.md)
- [start-delivery-execution.md](start-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
