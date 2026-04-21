# Show Delivery Initiatives

## Purpose

Show the project-wide delivery initiative summary for `Workspace Delivery ART`
through a supported read-only operator surface.

Use this when you need to inspect:

- which delivery initiatives currently exist
- which initiatives are still active versus `done`
- which initiatives are PI-scoped
- which initiatives carry blocked descendants
- which initiatives still carry `ready` items that violate the execution contract
- which initiatives carry unresolved or cross-initiative dependencies
- which initiatives already have PI objectives, ART risks, system-demo records,
  and inspect-and-adapt records
- which initiatives are already closeout-ready

This avoids opening each `Epic` one by one when the question is portfolio
visibility rather than editing.

## Session Start Rule

For any serious initiative already tracked in `Workspace Delivery ART`, start
the session here before reading repo code or resuming from chat memory.

Use this order:

1. `make openproject-show-delivery-initiatives`
2. `make openproject-check-delivery-art-quality`
3. `make openproject-show-delivery-execution TARGET_EPIC_ID=<epic-id>`

Truth split:

- ART = work-state truth
- owner repos = implementation and design truth
- `workspace-governance` = workspace-control truth

If the requested work is not already covered by the active ART:

- absorb it into the active item only when it is a tiny same-slice patch
- otherwise create a new item under the current `Epic` when it belongs to the
  same initiative
- route it through `Workspace Proposals` when it is a new initiative
- route repeated process or control misses into
  `workspace-governance/reviews/improvement-candidates/`
- route security or trust-boundary judgment through `security-architecture`

No meaningful delivery work should live only in chat once the initiative
exists in the ART.

## Command

Run from `platform-engineering/`:

```bash
make openproject-show-delivery-initiatives
```

Optional fields:

- `INCLUDE_DONE=true|false`
- `INCLUDE_PARKED=true|false`

Examples:

```bash
make openproject-show-delivery-initiatives \
  INCLUDE_DONE=false \
  INCLUDE_PARKED=false
```

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-show-delivery-initiatives \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7
```

## Expected Outcome

The command prints JSON with:

- project identity for `Workspace Delivery ART`
- summary counts for total, active, blocked, and closeout-ready initiatives
- closeout readiness that already accounts for missing completion evidence on
  `done` descendants
- summary counts for parked initiatives and parked descendants
- summary counts for dependency links, unresolved dependencies, and cross-initiative dependencies
- summary counts for PI objectives, ART risks, ready-contract gaps, and
  system-demo / inspect-and-adapt coverage
- summary counts by initiative status, `PM² Phase`, and `Target PI`
- portfolio rollups by delivery team, iteration, ROAM state, and PI objective type
- one entry per top-level delivery `Epic` with:
  - PM² governance visibility
  - execution summary counts
  - blocked descendant details
  - PI-objective and ART-risk visibility
  - ready-contract gap visibility
  - dependency summary counts
  - external dependency details
  - computed `closeout_ready` state

Default visibility:

- `INCLUDE_DONE=true` shows completed initiatives
- `INCLUDE_PARKED=false` keeps parked descendant details out of the per-initiative detail by default while still reporting parked counts

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- compare the top-level `Epic` list with the command output
- confirm `PM² Phase`, `Target PI`, and initiative status match the UI
- open any initiative reported as blocked, parked, or closeout-ready and verify the
  details match the current delivery tree
- confirm dependency counts and external dependency details match the relations shown on the affected work items
- run [check-delivery-art-quality.md](check-delivery-art-quality.md) before
  treating the ART as the current clean work queue

## Related References

- [start-delivery-execution.md](start-delivery-execution.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [show-delivery-planning.md](show-delivery-planning.md)
- [show-pi-objectives.md](show-pi-objectives.md)
- [manage-delivery-dependency.md](manage-delivery-dependency.md)
- [check-delivery-closeout-readiness.md](check-delivery-closeout-readiness.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
