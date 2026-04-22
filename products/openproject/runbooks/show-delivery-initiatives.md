# Show Delivery Initiatives

## Purpose

Show the project-wide delivery initiative summary for `Workspace Delivery ART`
through a supported read-only operator surface.

Use this when you need to inspect:

- which delivery initiatives currently exist
- which initiatives are still active versus inactive or `done`
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

Use this as the portfolio-selection and PI-replanning surface, not as the
default deep read for every active-coding turn.

Recommended order:

1. If the active `Epic` is already known:
   - `make openproject-show-delivery-active-front TARGET_EPIC_ID=<epic-id>`
   - `make openproject-check-delivery-art-quality TARGET_EPIC_ID=<epic-id>`
   - `make openproject-show-delivery-execution TARGET_EPIC_ID=<epic-id>` only when a deep read is needed
2. Use `make openproject-show-delivery-initiatives` when:
   - the active `Epic` is not yet known
   - you need a portfolio or PI-level view
   - you are replanning committed vs stretch work
   - you need to confirm initiative-level PM² governance across the ART

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
- `INCLUDE_INACTIVE=true|false`
  `INCLUDE_INACTIVE` now controls `retired` visibility only.

Examples:

```bash
make openproject-show-delivery-initiatives \
  INCLUDE_DONE=false \
  INCLUDE_INACTIVE=false
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
- summary counts for parked initiatives, retired initiatives, and inactive descendants
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

This is the deeper portfolio read. It is intentionally broader than the
broker-backed execution read and should not be the first command you reach for
when you already know the active initiative.

Default visibility:

- `INCLUDE_DONE=true` shows completed initiatives
- `parked` descendants remain visible by default because they are deferred open work
- `INCLUDE_INACTIVE=false` keeps only `retired` initiative or descendant
  details out of the per-initiative detail by default while still reporting
  retired counts

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- compare the top-level `Epic` list with the command output
- confirm `PM² Phase`, `Target PI`, and initiative status match the UI
- open any initiative reported as blocked, parked, retired, or closeout-ready and verify the
  details match the current delivery tree
- confirm dependency counts and external dependency details match the relations shown on the affected work items
- run [check-delivery-art-quality.md](check-delivery-art-quality.md) before
  treating the ART as the current clean work queue

## Related References

- [start-delivery-execution.md](start-delivery-execution.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [show-delivery-active-front.md](show-delivery-active-front.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [show-delivery-planning.md](show-delivery-planning.md)
- [show-pi-objectives.md](show-pi-objectives.md)
- [manage-delivery-dependency.md](manage-delivery-dependency.md)
- [check-delivery-closeout-readiness.md](check-delivery-closeout-readiness.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
