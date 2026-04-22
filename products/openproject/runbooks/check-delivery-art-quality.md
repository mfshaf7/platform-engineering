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
- `done` delivery work does not carry weak or malformed completion attestation
- `done` delivery work does not still have descendants outside `done` or
  `retired`
- active execution items do not violate the structured ready contract
- items explicitly marked `Not committed to a PI iteration yet.` do not also
  pretend to have concrete PI assignment or scheduled dates
- advisory narrative quality findings by work-item type:
  - `Epic`
    - `What This Initiative Achieves`
    - `Current PI Focus`
    - `Scope Boundaries`
    - `Execution Context`
  - `PI Objective`
    - `Outcome`
    - `Why This PI`
    - `Success Signal`
    - `Execution Context`
  - `Risk`
    - `Risk Event`
    - `Impact`
    - `Current Handling`
    - `Execution Context`
  - `Feature`
    - `What This Achieves`
    - `Benefit Hypothesis`
    - `Scope Boundaries`
    - `Execution Context`
  - `Enabler`
    - `What This Enables`
    - `Benefit Hypothesis`
    - `Scope Boundaries`
    - `Execution Context`
  - `User story` / `Task`
    - `What This Achieves`
    - `Why This Matters Now`
    - `Evidence Expectation`
    - `Execution Context`
  - `Milestone`
    - `Exit Condition`
    - `Execution Context`

Structural issues are hard failures.

That includes done-state attestation drift such as:

- description starts with loose prose instead of a heading
- description duplicates `Acceptance Criteria`, `Definition of Ready`, or
  `Definition of Done` as markdown headings
- active or done work is missing `Owner Repo`, `Assignee`, or `Responsible`

- `Completion Summary` written as a bullet list instead of a short paragraph
- `Changed Surfaces` not written as a flat bullet list
- `Test Result Evidence` bullets missing the required `PASS:` / `FAIL:` /
  `NOT APPLICABLE:` / `Attached artifact:` prefixes
- `Validation Evidence` bullets missing the required `PASS:` / `FAIL:` /
  `CHECK:` / `NOT APPLICABLE:` / `Attached artifact:` prefixes

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

- [standardize-delivery-art.md](standardize-delivery-art.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
