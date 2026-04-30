# Check Delivery ART Quality

## Purpose

Verify that the current `Workspace Delivery ART` records are clean enough to be
used as the primary work-state truth for a serious delivery session.

Use this as a scoped hygiene gate for the active initiative, and reserve the
full portfolio sweep for replanning, portfolio review, or governance cleanup.

Normal-session entrypoint:

1. broker workflow health
2. scoped ART quality
3. platform-admin repair only when projection or board state is the issue

Canonical machine-readable planning workflow contract:

- [delivery-art-planning-workflow.json](../delivery-art-planning-workflow.json)

Canonical machine-readable initiative-review workflow contract:

- [delivery-art-initiative-review-workflow.json](../delivery-art-initiative-review-workflow.json)

Canonical machine-readable blocker workflow contract:

- [delivery-art-blocker-workflow.json](../delivery-art-blocker-workflow.json)

When this quality check reports planning drift, read the matching gate id from
that contract before deciding whether the fix belongs in broker mutation
surfaces, roadmap projection, or operator procedure.

Planning-drift findings now include `gate_id` for the gates that map directly
to the machine-readable planning workflow contract.

## What It Checks

The supported quality check currently verifies:

- active initiatives carry the minimum PM² governance fields:
  - `PM² Phase`
  - `Sponsor`
  - `Business Objective`
  - `Success Criteria`
- initiatives in PM² `Closing` already carry `System Demo Evidence`
- initiatives in PM² `Closing` already satisfy the clean execution-state gate
- `done` initiatives remain in PM² `Closing`
- `done` initiatives retain `System Demo Evidence`
- `done` initiatives retain `Inspect & Adapt Actions`
- `done` initiatives still satisfy final closeout readiness
- `done` initiatives do not hide weak done-state narrative drift inside descendants
- `retired` initiatives do not hide open descendants outside `done` or `retired`
- non-done delivery work does not still carry completion-evidence sections
- `done` delivery work carries substantive completion evidence
- `done` delivery work does not carry weak or malformed completion attestation
- `done` delivery work does not carry weak done-state narrative structure,
  especially a broken `Execution Context`
- `done` delivery work does not still have descendants outside `done` or
  `retired`
- blocked delivery work carries a complete blocker record
- non-blocked delivery work does not still retain active blocker fields
- active execution items do not violate the structured ready contract
- items explicitly marked `Not committed to a PI iteration yet.` do not also
  pretend to have concrete PI assignment or scheduled dates
- `Target PI` and roadmap `version` do not diverge
- backlog or active work with blank `Target PI` still projects to the derived
  roadmap bucket `Not yet committed to a PI`
- retired work with blank `Target PI` projects to the derived roadmap bucket
  `Retired scope`
- retired work does not still retain stale `Target PI` commitment
- `PI Objective`, `User story`, `Task`, and `Milestone` records do not exist
  without PI commitment unless they have already moved into `retired` scope
- backlog `Feature` work does not already carry story-level execution children
- PI-committed non-`Epic` work carries a non-backlog `Iteration`
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
  - `Feature` / `User story` with `Execution Classification = Enabler`
    - `What This Enables`
    - `Benefit Hypothesis` for `Feature`
    - `Why This Matters Now` for `User story`
    - `Scope Boundaries` for `Feature`
    - `Evidence Expectation` for `User story`
    - `Execution Context`
  - `User story` / `Task`
    - `What This Achieves`
    - `Why This Matters Now`
    - `Evidence Expectation`
    - `Execution Context`
  - `Defect`
    - `What This Corrects`
    - `Why This Matters Now`
    - `Evidence Expectation`
    - `Execution Context`
  - `Milestone`
    - `Exit Condition`
    - `Execution Context`

Structural issues are hard failures.

That includes done-state attestation drift such as:

- legacy structural `Enabler` work items still present
- root-level non-`Epic` work items still present
- parent-child type relationships that violate the canonical taxonomy
- missing or invalid `Execution Classification` on `Feature` and `User story`
- semantic subject prefixes such as `Enabler:` or `Improvement:` that no longer
  match the machine type plus classification

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
- broker-reported `done_narrative_contract_*` drift on done items, including:
  - missing required done-state narrative headings
  - empty required narrative sections
  - `Execution Context` that is not a flat bullet list
  - `Execution Context` that no longer matches stored owner, parent, delivery
    team, or iteration values

Narrative findings are advisory only for epic and non-done execution work. Once
an item is `done`, narrative-quality drift is a hard failure through the
broker-reported done-state contract.

Advisory narrative findings still matter for non-done work:

- `rewrite-required`
  - too weak to operate safely on the active slice
- `discussion-required`
  - directionally right but ambiguous enough to discuss before active or
    next-up execution continues
- `polish`
  - usable, but weak enough to clean up later

Planned backlog decomposition is intentionally lighter than executable work.
Loose prose on a `new` or `parked` backlog `Feature`, `User story`, `Defect`,
or `Risk` is reported as backlog `polish` while it has no `Target PI` and no
concrete iteration. It becomes a hard quality issue only when that item is
promoted into executable, PI-committed, blocked, or done scope.

To keep the default operator output small, backlog `polish` details are
summarized by count. Set `INCLUDE_POLISH_DETAILS=true` only when you are
intentionally cleaning backlog prose.

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
- `INCLUDE_POLISH_DETAILS=true|false`
  - include the full backlog-polish list instead of the default compact
    summary

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7
```

The checker now reads the broker-owned delivery-session quality pack instead of
pushing a direct Rails dump into the OpenProject pod. It remains the supported
platform quality wrapper, but its normal read path is broker-native.

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

The quality check also verifies PI-commitment hygiene:

- PI-assigned work must project into the matching roadmap `version`
- work without `Target PI` must project into the correct derived roadmap bucket
- backlog or active scope uses `Not yet committed to a PI`
- retired scope uses `Retired scope`
- non-`Epic` work in `ready`, `in-progress`, or `blocked` must not stay in
  that unassigned backlog bucket
- `PI Objective`, `User story`, `Task`, and `Milestone` work must not stay
  uncommitted even in `new`
- backlog `Feature` work must stay backlog-shaped until PI commitment

If the only failure is roadmap `version` projection drift after a broker or
platform-admin ART mutation, do not treat that as new planning scope. Run
`make openproject-sync-delivery-art-views PI_NAMES="<known-pi-names>"` with the
proven active ART runtime context, then rerun this quality gate. Projection sync
is required after any mutation that can move work between committed, backlog,
done, parked, or retired roadmap buckets, not only after direct `Target PI`
updates.
- PI-committed non-`Epic` work must also carry a non-backlog `Iteration`
- blocked work must use the bounded blocker workflow instead of generic status
  drift

Typical fields include:

- checked initiative count
- quality issue totals by class
- advisory narrative-finding totals by type and severity
- whether active or next-up work needs discussion before execution continues
- affected initiative ids
- per-item violation details for remediation

## Related References

- [check-delivery-art-workflow-health.md](check-delivery-art-workflow-health.md)
- [standardize-delivery-art.md](standardize-delivery-art.md)
- [plan-delivery-art.md](plan-delivery-art.md)
- [manage-delivery-blockers.md](manage-delivery-blockers.md)
- [review-delivery-initiative.md](review-delivery-initiative.md)
- [openproject-platform-admin-surface.md](openproject-platform-admin-surface.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
