# Delivery ART Contract

## Purpose

Define the canonical OpenProject delivery plane for work that has already been
accepted in `Workspace Proposals` and now needs enterprise execution tracking.

This contract is intentionally separate from:

- `idea-backlog-contract.md`

The proposal backlog remains the intake plane. This contract defines the
delivery plane.

## Work-State Authority

Once work is already tracked inside `Workspace Delivery ART`, the delivery ART
becomes the primary work-state system of record for that initiative.

Truth split:

- `Workspace Delivery ART`
  - work-state truth
- owner repos
  - implementation and design truth
- `workspace-governance`
  - workspace-control truth

That means the operator should start new serious-project sessions from the ART
initiative summary instead of reconstructing scope from chat or handoff prose.
Chat and handoff notes remain useful context, but they are not the official
delivery queue once the initiative exists in the ART.

## Out-Of-Coverage Routing

When a request is not already covered by the active ART:

- absorb it into the active work item only when it is a tiny same-slice patch
- add a new in-scope ART item when it belongs to the same initiative and needs
  its own evidence, ownership, or sequencing
- route it back through `Workspace Proposals` when it is really a new
  initiative
- route repeated control or process misses into
  `workspace-governance/reviews/improvement-candidates/`
- route security or trust-boundary judgment through `security-architecture`
  and reflect the execution impact back into the ART as a blocker, risk, or
  new task when needed
- leave pure owner-repo maintenance outside the initiative in the owner repo

No meaningful delivery work should live only in chat once the ART exists.

## Narrative Quality Discussion Gate

Narrative quality should not be left to silent personal judgment once the ART
is being used as delivery truth.

Use a two-layer model:

- hard gate
  - structural hygiene and deterministic field-state checks
- discussion gate
  - narrative weakness that is deterministic enough to flag, but still needs
    operator judgment before rewrite

Narrative findings do not automatically fail the ART-quality check for active
or not-yet-done work. They are advisory findings with explicit severity:

- `rewrite-required`
  - too weak to operate safely on the active slice
- `discussion-required`
  - directionally right, but ambiguous enough to discuss before active or
    next-up execution continues
- `polish`
  - usable, but weak enough to clean up later

When an active or next-up item carries `rewrite-required` or
`discussion-required`, the operator workflow should raise that finding
explicitly before continuing the item.

Once an item is `done`, the same narrative standard stops being advisory. Weak
done-state narrative becomes a hard ART-quality failure because the closeout
record is now evidence, not just planning prose.

## Narrative Rubric

Required narrative sections by type:

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
- `User story`
  - `What This Achieves`
  - `Why This Matters Now`
  - `Evidence Expectation`
  - `Execution Context`
- `Feature` or `User story` with `Execution Classification = Enabler`
  - `What This Enables`
  - `Benefit Hypothesis` for `Feature`
  - `Why This Matters Now` for `User story`
  - `Scope Boundaries` for `Feature`
  - `Evidence Expectation` for `User story`
  - `Execution Context`
- `Defect`
  - `What This Corrects`
  - `Why This Matters Now`
  - `Evidence Expectation`
  - `Execution Context`
- `Task`
  - `What This Achieves`
  - `Why This Matters Now`
  - `Evidence Expectation`
  - `Execution Context`
- `Milestone`
  - `Exit Condition`
  - `Execution Context`

These sections exist to make the record operationally safe to use as delivery
truth. They are not free-form writing polish targets.

Description rules:

- start the description with a markdown heading instead of loose prose
- keep `Acceptance Criteria`, `Definition of Ready`, and `Definition of Done`
  in custom fields only
- use `Execution Context` for the fast human-readable bridge to repo, review,
  runtime, or operator surfaces

Done-state narrative rules:

- completed items must still satisfy the required narrative headings for their
  type
- required done-state narrative sections must not be empty
- `Execution Context` must stay a flat bullet list
- `Execution Context` must preserve the stored:
  - `Owner repo`
  - `Parent item` when the work item has a parent
  - `Delivery team` when that field is set
  - `Iteration` when that field is set
- the broker and ART quality checker now fail closed when that done-state
  narrative contract drifts

## Canonical Delivery Project

Phase 1 should use one OpenProject delivery project:

- display name: `Workspace Delivery ART`
- identifier: `workspace-delivery-art`

This project is intended to hold:

- consumed accepted ideas that have entered real delivery management
- PM²-governed top-level initiatives
- SAFe-aligned execution work below those initiatives
- PI planning and Kanban execution views

It should not be used for:

- raw idea capture
- proposal triage
- parked proposal backlog items
- release evidence or governed rollout attestation

## Methodology Model

Use:

- `PM²` for enterprise governance of the top-level consumed initiative
- a SAFe-aligned one-ART model for execution structure
- Kanban boards for execution visualization

This means the delivery project is not a second proposal backlog and not a
plain task board.

The initial platform bootstrap for this project should provision the canonical
project, work package types, execution statuses, required custom fields, and
the operator-visible board surface supported by the current runtime. Program
Increment versions should be created from explicit PI operator input or from
real delivery records that already carry `Target PI`. The writable placement
signal for delivery work items is `Target PI`; versions exist to declare the PI
set and back the managed board/view structure.

## One-ART Shape

The first delivery implementation should model one `Agile Release Train`.

SAFe-aligned mapping in OpenProject:

- project:
  - one ART
- versions:
  - Program Increments
- work package hierarchy:
  - `Epic`
  - `PI Objective`
  - `Feature`
  - `User story`
  - `Defect`
  - `Task`
  - `Milestone`
  - `Risk`
- `Execution Classification` on `Feature` and `User story`:
  - `Business`
  - `Enabler`
  - `Improvement`
- boards:
  - Kanban execution views

Multiple ARTs are deferred until the single-ART model is proven useful.

## PM² Governance Overlay

Each consumed accepted idea should create one top-level delivery initiative in
the ART project.

Recommended top-level type:

- `Epic`

That top-level item should carry a `PM² Phase` field with these values:

- `Initiating`
- `Planning`
- `Executing`
- `Closing`

Recommended additional governance fields on the top-level initiative:

- `Origin Idea Ref`
- `Sponsor`
- `Business Objective`
- `Success Criteria`
- `Target PI`
- `System Demo Evidence`
- `Inspect & Adapt Actions`
- initiative-level `NFR Category` when the whole initiative is dominated by one non-functional concern

The PM² phase is not the same thing as Kanban execution status.

PM² governance fields are initiative-level controls.

They apply directly to the top-level delivery `Epic`, not to every child
`Feature`, `User story`, `Defect`, or `Task`.

Child delivery work should instead carry:

- execution `status`
- `Target PI`
- `start date`
- `due date`
- `work`
- `remaining work`
- `% complete`
- assignee or responsible owner
- `Owner Repo`

For broker-backed create and update surfaces, an assignee login is valid only
when OpenProject exposes that principal as assignable in the target project or
work-item form. The delivery workflow contract should not promise arbitrary
user assignment outside that backend rule.
- `Delivery Team`
- `Iteration`
- `Acceptance Criteria`
- `Definition of Ready`
- `Definition of Done`
- work-item `NFR Category` when relevant
- blockers, parking, and dependency state when relevant

If a child work item needs PM² context, read it from the parent initiative or
from the supported initiative summaries instead of duplicating PM² governance
into child-record fields or repeated child-description boilerplate.

The delivery-art bootstrap should enforce this directly by scoping initiative
governance fields to the `Epic` type so they do not appear on child work-item
forms in the UI.

In the current v1 UI, `PM²` appears as:

- the top-level delivery `Epic`
- field `PM² Phase`
- companion governance fields such as `Sponsor`, `Business Objective`,
  `Success Criteria`, and `Target PI`
- board `PM² Phase Board`

There is no separate PM² plugin package here. The governance overlay is carried
by the delivery record shape itself plus the managed `PM² Phase Board`
view.

## Runtime Board Boundary

The current platform packages OpenProject Community Edition.

That means the delivery project cannot rely on the native enterprise
`status`/`version` action-board types. The supported board model here is:

- `board_view` enabled on the project
- basic-board presets backed by public project queries
- project versions used to declare the Program Increment set
- `Target PI` used as the writable work-item placement field for PI planning
  and PI objective views

So the canonical runtime surface is:

- `ART Dashboard`
- `PM² Phase Board`
- `ART Execution Kanban`
- `PI Objectives` when PI versions exist
- `ART Risk Register`

Planning remains a supported read-model/report surface through:

- `show-delivery-planning`
- `show-delivery-initiatives`
- `show-pi-objectives`

The operator surface must also expose project-wide initiative visibility, not
only per-epic drill-down. Operators should be able to inspect which delivery
initiatives are active, blocked, PI-scoped, or already closeout-ready without
opening each initiative individually.

The supported operator surface should also expose:

- a team-and-iteration planning summary for one initiative
- a reviewable batch execution-update surface for iteration, team, PI, assignee,
  schedule, and progress changes
- a PI-objective review surface with committed/stretch visibility and planned
  versus actual business-value rollups plus explicit review outcome recording
- explicit system-demo and inspect-and-adapt recording workflows on the
  initiative record
- an ART-quality check that can verify initiative and work-item hygiene before
  the operator treats the ART as current truth

## Execution Status Model

Execution tracking should stay separate from proposal lifecycle.

Recommended initial Kanban-oriented execution statuses:

- `new`
- `ready`
- `in-progress`
- `blocked`
- `parked`
- `retired`
- `done`

These statuses apply to delivery work in the ART project, not to proposal
records in `Workspace Proposals`.

`parked` is the deferred-only state for delivery work that is intentionally
removed from the current active front for possible later return.

`retired` is the terminal state for delivery work that is duplicate, mistaken,
superseded, absorbed, invalid, or otherwise not returning to active scope.

Neither `parked` nor `retired` counts as active execution work.

`parked` is still open deferred work:

- it should remain visible in all-open execution and portfolio views by default
- it should still block initiative closeout

`retired` is terminal inactive work:

- it should stay out of normal open-scope views by default
- it should not block initiative closeout on its own

## Blocker / Impediment Governance

`blocked` is an execution visibility state, not a sufficient enterprise record
by itself.

When delivery work is blocked, the delivery plane should also capture:

- blocker statement
- impact on the affected delivery item or initiative
- blocker owner
- discovered date
- decision path:
  - `remove`
  - `workaround`
  - `accept-risk`
  - `defer`
- justification for the chosen path

If the blocker is not removed immediately:

- record a follow-up owner
- record a review date
- keep the reasoning visible from the delivery record or its linked blocker record

Workaround, accepted-risk, and defer paths must not live only in chat memory or
board labels.

Risks are not the same thing as blockers.

Use the `Risk` type plus ROAM fields when the concern is broader than one
execution item and needs ART-level visibility or PI review.

Recommended `Risk` fields:

- `ROAM State`
  - `Resolved`
  - `Owned`
  - `Accepted`
  - `Mitigated`
- `Risk Owner`
- `Risk Review Date`
- `Risk Disposition`

Blockers remain item-local execution impediments. Risks carry ART-level or
PI-level exposure and are expected to survive beyond one blocked item when
necessary.

## SAFe Planning And Prioritization Fields

The delivery plane must also carry the core SAFe planning metadata, not only
execution statuses.

Recommended planning fields by type:

- `PI Objective`
  - `PI Objective Type`
    - `Committed`
    - `Stretch`
  - `PI Objective Review Outcome`
    - `Met`
    - `Partially met`
    - `Not met`
  - `Planned Business Value`
  - `Actual Business Value`
  - `Acceptance Criteria`
- `Feature`
  - `Acceptance Criteria`
  - WSJF component fields
    - `WSJF User-Business Value`
    - `WSJF Time Criticality`
    - `WSJF Risk Reduction / Opportunity Enablement`
    - `WSJF Job Size`
    - computed `WSJF Score`
- `Feature`
  - `Acceptance Criteria`
  - `Execution Classification`
  - `NFR Category` when the feature is primarily non-functional work
- `User story`
  - `Acceptance Criteria`
  - `Definition of Ready`
  - `Definition of Done`
  - `Iteration`
  - `Execution Classification`
- `Defect` / `Task`
  - `Acceptance Criteria`
  - `Definition of Ready`
  - `Definition of Done`
  - `Iteration`

These fields are part of the supported operator model and should not be left to
ad hoc free-text when the structured field exists.

## Ready Contract Enforcement

Moving a delivery work item to `ready` is not only a status change.

The supported broker-backed workflows for create, update, and plan-apply
should reject `ready` when the item still lacks the required structured
execution fields for its type.

Minimum `ready` expectations are:

- `Feature`, `User story`, `Defect`, `Task`
  - `Delivery Team`
  - `Iteration`
  - `Execution Classification` for `Feature` and `User story`
  - `Acceptance Criteria`
  - `Definition of Ready`
  - `Definition of Done`
- `PI Objective`
  - the same execution fields as above
  - `PI Objective Type`
  - `Planned Business Value`
  - `Actual Business Value`
- `Risk`
  - `Delivery Team`
  - `Iteration`
  - `ROAM State`
  - `Risk Owner`
  - `Risk Review Date`
  - `Risk Disposition`

This should be enforced through the supported operator surfaces instead of
leaving `ready` discipline to manual UI review.

## Initiative Review Workflows

`System Demo Evidence` and `Inspect & Adapt Actions` are initiative-level
fields, but they should not be treated as one-shot static text only.

The supported operator surface should allow timestamped append-only recording
for:

- one system-demo entry
- one inspect-and-adapt entry

so the initiative record can accumulate PI review history without forcing the
operator to rewrite the entire field body each time.

## Work Item Completion Evidence

Moving a delivery work item to `done` is not only a status change.

A completed work item should also carry explicit proof of completion in the
record itself. Minimum completion evidence for a `done` child work item is:

- completion summary
- changed surfaces
- test result evidence
- validation evidence

Use these sections for different purposes:

- `Completion Summary`
  - describe the completed outcome in plain operator language
  - do not repeat the file or surface inventory here
- `Changed Surfaces`
  - list the concrete files, contracts, docs, endpoints, or other changed
    surfaces
- `Test Result Evidence`
  - summarize the relevant test outcome briefly and mention any attached raw
    artifact
- `Validation Evidence`
  - record the broader validation commands or checks that proved the finished state

Completion evidence uses a separate purpose from the execution narrative and
from running operator notes:

- execution narrative
  - sections such as `What This Achieves`, `What This Enables`,
    `Benefit Hypothesis`, `Evidence Expectation`, or `Execution Context`
  - describe the intended result before the item is done
- operator work notes
  - timestamped running notes, reopen history, and live observations
  - useful for execution history, but not the canonical done attestation
- completion attestation
  - the required done-state proof block described here
  - this is the canonical closeout record

Structured execution fields remain outside the markdown description:

- `Acceptance Criteria`
- `Definition of Ready`
- `Definition of Done`

Those three belong in OpenProject custom fields so the ART can validate and
query them consistently. Do not mirror them back into markdown headings inside
the description body. A work item should not render those sections twice in the
UI.

Formatting standard for the completion attestation:

- `Completion Summary`
  - one short paragraph
  - outcome-first
  - do not use bullet-list formatting
- `Changed Surfaces`
  - flat bullet list only
  - list the concrete files, contracts, docs, endpoints, runtime surfaces, or
    boards/views changed
- `Test Result Evidence`
  - flat bullet list only
  - every bullet must start with:
    - `PASS:`
    - `FAIL:`
    - `NOT APPLICABLE:`
    - `Attached artifact:`
- `Validation Evidence`
  - flat bullet list only
  - every bullet must start with:
    - `PASS:`
    - `FAIL:`
    - `CHECK:`
    - `NOT APPLICABLE:`
    - `Attached artifact:`
- optional `Residual Follow-Up`
  - flat bullet list only
  - use this only when the done item deliberately hands off explicit remaining
    work
  - every bullet must reference an explicit ART item or work package such as
    `#179` or `openproject://work_packages/179`

The best current directional example is `Task #62`, but the target standard is
stricter than historical examples that only satisfied the minimum section
presence check.

These should be recorded through the supported operator workflow, not left as
implicit chat memory or only in a transient CLI log.

When the work has a discrete test run or command output worth preserving, the
completion workflow should also attach that artifact to the work item itself so
the record carries both:

- a short test result statement in the description
- the attached raw output or report file when one exists

Do not create a standalone `Attachments` section. Attachments should be named
inside the evidence section they support so the record explains what each file
proves.

For work that is not yet complete, the record should state that completion
evidence is not yet applicable instead of silently omitting the section.

Initiative closeout readiness should treat missing completion evidence on
`done` descendants as a failure, not just missing documentation. Weakly
formatted completion evidence should also fail closeout readiness and ART
quality checks when it no longer reads like a disciplined delivery attestation.
The same is now true for weak done-state narrative structure, especially a
broken `Execution Context`.

## Dependency Governance

Execution dependencies between delivery items must be explicit and inspectable.

Use dependency links when one delivery item cannot proceed until another item
finishes. Operator semantics are:

- target work item depends on predecessor work item

The underlying OpenProject storage uses `follows`, but the operator workflow
must expose dependency language, not raw relation internals.

The supported operator surface should allow:

- add or remove one dependency
- optional lag and dependency note
- recursive execution visibility that shows:
  - dependency counts
  - unresolved dependencies
  - cross-initiative dependencies when they exist

Dependency state must be visible from the supported CLI summaries, not only from
manual UI inspection.

## Parking / Retirement Governance

Delivery work that is mistaken, superseded, or intentionally deferred must not
be deleted or left as silent active scope.

Use explicit inactive-scope governance:

- parking decision:
  - `defer`
  - `retire`
- parking reason
- parking review date when the decision is `defer`
- retirement reason when the decision is `retire`
  - `superseded`
  - `duplicate`
  - `invalid`
  - `absorbed`
  - `cancelled`

Deferred items move to `parked`. Retired items move to `retired`.

`superseded` is a retirement reason, not a primary execution status.

Parking or retirement transitions remove the item from the current active front
while keeping the record auditable. Deferred items remain reversible. Retired
items are terminal unless deliberately re-opened through a future operator
workflow.

## Intake Boundary

The intake point into the delivery project is:

- `accepted` in `Workspace Proposals`

Rules:

- an accepted proposal does not become delivery work in place
- consumption into the ART is an explicit promotion step
- the source proposal remains the proposal-of-record
- the ART record becomes the execution-of-record

## Consumption Mapping

When an accepted idea is consumed into the delivery ART, copy at least:

- title
- captured body
- triage summary
- operator decision notes
- internal evaluation metadata:
  - suspected owner
  - affected scope
  - trust boundary areas
  - confidence
  - AI assist lane
  - notes
- source proposal reference

Add delivery-only fields in the ART project:

- `PM² Phase`
- `Origin Idea Ref`
- `Target PI`
- delivery execution status

## Link Contract

The proposal and delivery records must keep explicit backlinks.

Source proposal should store:

- `delivery_ref`

ART delivery record should store:

- `origin_idea_ref`

These links should be durable and readable from both OpenProject and the broker
projection.

## Lifecycle Synchronization

Proposal lifecycle and delivery lifecycle remain distinct.

Rules:

- source proposal stays `accepted` while delivery is active
- source proposal moves to `implemented` only when delivery closes with a real
  realized outcome
- delivery closeout requires the top-level epic to be `done`, with no open
  descendants outside `done` or `retired`, and no active blocker records
  remaining under that epic
- source proposal may move to `superseded` if a newer accepted record replaces
  it
- delivery execution statuses must not be pushed back into proposal status

## Production Activation Hygiene

If this delivery plane is later activated in a real `prod` environment, it
must be noise-free and provenance-safe.

That means:

- no dev-integration rehearsal epics
- no governed stage proof records
- no placeholder PI values carried over as if they were real production plans
- no copied backlinks from local or stage rehearsal
- no test blocker records or fabricated PM² governance data

Allowed existing production-plane history:

- real production delivery epics already created there
- vetted historical imports with explicit provenance
- an explicitly approved promoted delivery baseline, including the current
  validated ART history when it is being carried into production deliberately

Production delivery history still must originate from real accepted production
proposals, explicit curated imports, or an approved promoted baseline, not
smoke, demo, or rehearsal-only consume runs.

## Initial Operating Model

Phase 1 should start with explicit manual consumption, not automatic sync.

That means:

- operator approves the proposal in `Workspace Proposals`
- operator or broker creates the top-level delivery initiative explicitly
  through the broker-owned delivery workflow
- backlinks are recorded
- execution proceeds inside the ART project

The initial platform bootstrap must create the delivery-art board surface that
the current runtime actually supports. PI versions can still be absent until
real PI names are supplied or real delivery records carry `Target PI`.

Broker-backed creation and governance updates should preserve the same link
and governance model.

## Deferred In Phase 1

- multiple ARTs
- solution-train views
- automatic bidirectional synchronization
- direct Telegram delivery management commands
- governed stage rehearsal for this new delivery model before the concrete
  runtime shape exists
