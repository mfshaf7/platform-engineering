# Check Delivery ART Quality

## Purpose

Verify that the current `Workspace Delivery ART` records are clean enough to be
used as the primary work-state truth for a serious delivery session.

Use this as a scoped hygiene gate for the active initiative, and reserve the
full portfolio sweep for replanning, portfolio review, or governance cleanup.

## What It Checks

The supported quality check currently verifies:

- active initiatives carry the minimum PM² governance fields:
  - `PM² Phase`
  - `Sponsor`
  - `Business Objective`
  - `Success Criteria`
- non-done delivery work does not still carry completion-evidence sections
- `done` delivery work carries substantive completion evidence
- active execution items do not violate the structured ready contract
- items explicitly marked `Not committed to a PI iteration yet.` do not also
  pretend to have concrete PI assignment or scheduled dates
- advisory narrative quality findings by work-item type:
  - `Epic`
    - `Current PI Focus`
    - `Scope Boundaries`
  - `PI Objective`
    - `Outcome Statement`
    - `Why This PI`
    - `Success Signal`
  - `Risk`
    - `Trigger`
    - `Impact`
    - `Disposition`
  - `Feature`
    - `Delivery Outcome`
    - `Scope Boundaries`
  - `Enabler`
    - `Delivery Outcome`
    - `Runway Need`
  - `User story` / `Task`
    - `Concrete Output`
    - `Evidence Expectation`
  - `Milestone`
    - `Exit Condition`

Structural issues are hard failures.

Narrative findings are advisory, but they still matter:

- `rewrite-required`
  - too weak to operate safely on the active slice
- `discussion-required`
  - directionally right but ambiguous enough to discuss before active or
    next-up execution continues
- `polish`
  - usable, but weak enough to clean up later

## Command

Run from `platform-engineering/`:

```bash
make openproject-check-delivery-art-quality
```

Optional fields:

- `TARGET_EPIC_ID=<epic-id>`
  - limit the check to one initiative
  - recommended for routine active-session startup
- `INCLUDE_DONE=true|false`
  - include or skip fully done initiatives in the portfolio sweep

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7
```

## Expected Outcome

The command prints a JSON quality report and exits:

- `0` when the checked initiative scope is clean
- non-zero when one or more quality violations were found

Narrative findings do not change the exit code by themselves. They are a
discussion gate, not a structural failure gate.

Quality modes:

- full portfolio sweep
  - no `TARGET_EPIC_ID`
  - validates initiative-level PM² governance plus execution hygiene
- scoped execution check
  - `TARGET_EPIC_ID=<epic-id>`
  - validates execution hygiene and narrative quality for the active initiative
  - preferred for routine session startup when the active `Epic` is already known

Typical fields include:

- checked initiative count
- quality issue totals by class
- advisory narrative-finding totals by type and severity
- whether active or next-up work needs discussion before execution continues
- affected initiative ids
- per-item violation details for remediation

## Related References

- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
