# Delivery ART Contract

## Purpose

Define the canonical OpenProject delivery plane for work that has already been
accepted in `Workspace Proposals` and now needs enterprise execution tracking.

This contract is intentionally separate from:

- `idea-backlog-contract.md`

The proposal backlog remains the intake plane. This contract defines the
delivery plane.

`Target PI` is the canonical writable PI-placement field. OpenProject
`version` is a required derived projection used for roadmap compatibility.

Projection rules:

- when `Target PI` is populated, `version` must match that PI exactly
- when `Target PI` is blank on backlog or active scope, `version` must project
  to the derived backlog bucket `Not yet committed to a PI`
- when `Target PI` is blank on retired scope, `version` must project to the
  derived retired bucket `Retired scope`
- the derived backlog bucket is only for uncommitted backlog posture; non-`Epic`
  work must carry `Target PI` before it moves to `ready`, `in-progress`, or
  `blocked`

That keeps the OpenProject roadmap page truthful to the whole ART instead of
only the subset that already carries PI assignment.

## Initiative Family And Lineage

One ART portfolio may contain multiple valid initiative families.

What must stay coherent is not “same project = same story”, but the top-level
lineage model for each `Epic`.

Canonical machine-readable lineage contract:

- `products/openproject/delivery-art-initiative-lineage.json`

Primary operator surface:

- [runbooks/manage-delivery-initiative-lineage.md](runbooks/manage-delivery-initiative-lineage.md)

Top-level `Epic` work now carries four lineage fields:

- `Initiative Family`
- `Lineage Role`
- `Architecture Anchor Ref`
- `Required Upstream Ref`

The only allowed temporary exception is a brand-new initiative shell that is
still:

- `status = new`
- `PM² Phase = Initiating`
- blank `Target PI`
- blank lineage fields

Once a top-level initiative moves beyond that shell posture, it must declare
its family and lineage role. Roles then govern whether anchor and upstream refs
are mandatory.

Managed family views exist so the portfolio no longer has to be read as one
flat storyline:

- `Initiative Family Board`
- `Initiative Family / <family>` queries

## Supported Delivery Surfaces

Normal `Workspace Delivery ART` work should now use the broker-owned delivery
workflow in
[`operator-orchestration-service`](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
for:

- session bootstrap
- workflow health
- scoped ART quality/readiness reads
- planning repair
- work-item continuation and closeout
- initiative review and guided initiative closeout

The remaining OpenProject product runbooks and scripts in this directory are
platform-admin surfaces only. They remain valid for:

- bootstrap and schema provisioning
- board and roadmap projection repair
- one-time normalization after contract changes
- identity and admin repair
- clean-start verification

Canonical machine-readable admin-surface contract:

- `products/openproject/openproject-platform-admin-surface.json`

They are not the supported day-to-day ART execution surface anymore.

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

- start the description with a markdown heading instead of loose prose before
  the item becomes executable, PI-committed, blocked, or done
- planned backlog `Feature`, `User story`, `Defect`, and `Risk` items may carry
  lightweight planning prose while they remain `new` or `parked`, have no
  `Target PI`, and have no concrete iteration; the quality checker reports
  that as backlog `polish`, not as a hard ART failure
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
set, back the managed board/view structure, and expose one derived backlog
bucket for work that is not yet committed to any PI.

## One-ART Shape

The first delivery implementation should model one `Agile Release Train`.

SAFe-aligned mapping in OpenProject:

- project:
  - one ART
- versions:
  - Program Increments plus one derived roadmap bucket for work that is not
    yet committed to a PI
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

## Consume-To-PI-Planning Workflow

Canonical machine-readable workflow contract:

- `products/openproject/delivery-art-planning-workflow.json`

That contract is the phase-and-gate source for:

- `runbooks/plan-delivery-art.md`
- `scripts/openproject_check_delivery_art_quality.py`
- broker-side planning metadata in `operator-orchestration-service`
- workspace-level cross-repo drift validation in `workspace-governance`

Canonical machine-readable blocker workflow contract:

- `products/openproject/delivery-art-blocker-workflow.json`

That contract is the trigger-and-gate source for:

- `runbooks/manage-delivery-blockers.md`
- blocker-related ART quality checks
- broker-side blocker workflow metadata in `operator-orchestration-service`
- workspace-level cross-repo drift validation in `workspace-governance`

Use one governed planning path for newly accepted work:

1. Consume
   - accepted work enters `Workspace Delivery ART` as one top-level `Epic`
   - the consume step creates the initiative shell only
   - do not auto-create PI objectives, user stories, tasks, or deep execution
     trees during consume
2. Initiative framing
   - define the initiative narrative, scope boundaries, and owner path on the
     `Epic`
   - add only backlog-shaped child work while the initiative is still
     uncommitted:
     - `Feature`
     - `Risk`
     - `Defect` only when it is explicitly being held as uncommitted backlog
       correction work
3. PI planning
   - assign `Target PI` to the initiative once the current PI focus is real
   - create `PI Objective` items for that PI
   - create only the committed `Feature` and `Risk` slices for that PI
   - create or select a new PI only for a new planning horizon, accepted
     carryover target, or closed/current-PI boundary; high child item count is
     not itself a reason to split the PI
   - do not PI-commit initiative scope unless at least one `PI Objective`
     exists in the same initiative
   - committed non-`Epic` work must carry:
     - `Target PI`
     - non-backlog `Iteration`
     - owner and assignment fields
   - committed `Iteration` must align to the same `Target PI`, or use an
     explicitly allowed `Program-wide / ...` iteration label
4. Rolling-wave elaboration
   - create `User story` work under backlog features only as `new`,
     non-executable future decomposition with blank `Target PI`
   - create executable `User story` work only for committed features
   - create `Task` work only under active `User story` or `Defect` items
   - each PI-committed `Feature` must already have at least one open
     `User story` or `Defect` child as its executable leaf front
   - do not pre-expand backlog features into executable story forests before
     PI commitment
5. Execution
   - treat the active child `User story`, `Defect`, or `Task` as the real
     execution front
   - do not present a `Feature` or `PI Objective` shell as the executable next
     item when it still has open child work
6. PI review, carryover, and decommit
   - explicitly close completed PI objectives and work items with evidence
   - re-target true carryover work to the next PI instead of leaving stale PI
     placement behind
   - move decommitted work back to backlog posture instead of leaving it
     looking committed

This keeps consume, planning, execution, and the roadmap projection aligned to
one deliberate workflow instead of relying on later cleanup.

### Phase Checklist And Gate Rule

Every phase must stay explicit in two forms:

- operator checklist
  - what the operator is allowed to create, update, or defer in that phase
- control gate
  - the machine or operator checkpoint that blocks drift from that phase

The runbook is the primary operator surface. The JSON contract is the
machine-readable phase and gate inventory. Do not let either side drift or
exist on its own.

## Planning Gates

Use these commitment rules as the canonical machine model:

- `Epic`
  - may exist without `Target PI`
  - is the only allowed root work-item type
- `Feature`
  - may exist without `Target PI` while it stays backlog-shaped
  - backlog features may carry `new` planned `User story` children only while
    those children remain non-executable future decomposition with blank
    `Target PI`
  - once PI-committed, a `Feature` must keep at least one open `User story`
    or `Defect` child
- `Risk`
  - may exist without `Target PI`
- `Defect`
  - may exist without `Target PI` only while it remains backlog correction work
    in `new` posture
- `PI Objective`
  - must carry `Target PI` unless it has already moved into `retired` scope
  - at least one `PI Objective` must exist before an initiative can keep
    PI-committed non-`Epic` scope
- `User story`
  - may exist without `Target PI` only as `new` or `parked` planned backlog
    decomposition under a backlog `Feature`
  - must carry `Target PI` once executable, active, or PI-committed
- `Task`
  - must carry `Target PI` unless it has already moved into `retired` scope
- `Milestone`
  - must carry `Target PI` unless it has already moved into `retired` scope
  - remains an `Epic`-level checkpoint, not an execution container
  - does not replace a `PI Objective` or a `Feature` leaf front

Committed non-`Epic` work must also carry a non-backlog `Iteration`.

Lightweight PI lifecycle rules:

- PI lifecycle states are `planning`, `active`, `closing`, and `closed`
- the current enforcement mode is WIP-front-limited, not story-point capacity
  accounting
- a new PI is created or selected for a new planning horizon, accepted
  carryover target, or closed/current-PI boundary
- child item volume alone does not create a new PI
- when `Target PI` is set, `Iteration` must either start with the same PI name
  followed by ` / ` or use an allowed `Program-wide / ...` label
- a mismatch such as `Target PI = PI-2026-03` with
  `Iteration = PI-2026-02 / Iteration 1` is invalid
- carryover at PI review must be re-targeted to the next PI or explicitly
  decommitted back to backlog posture

Derived roadmap rules:

- `Target PI` is canonical planning truth
- OpenProject `version` is a derived roadmap projection
- blank `Target PI` on backlog or active scope projects to `Not yet committed
  to a PI`
- blank `Target PI` on retired scope projects to `Retired scope`
- retired scope must not retain stale `Target PI`; retirement clears PI
  commitment and returns the item to the canonical uncommitted iteration label
- the unassigned roadmap bucket is for backlog posture only, not active
  execution
- the retired roadmap bucket is for inactive superseded or withdrawn scope, not
  current PI commitment
- projection reconciliation is part of the workflow after any mutation that can
  move work between roadmap buckets, including PI assignment or clearing,
  carryover, decommit, parking, retirement, completion, and platform-admin
  repair; use the broker projection checkpoint and run scoped sync before
  treating the scoped quality gate as final

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

`retired` is not a PM² phase. It is a terminal initiative status that sits
beside the PM² success path.

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
view, which now includes a dedicated `Retired` terminal lane.

## PM² Initiative Review And Closing Workflow

Canonical initiative-review workflow contract:

- [delivery-art-initiative-review-workflow.json](delivery-art-initiative-review-workflow.json)

Primary operator surface:

- [runbooks/review-delivery-initiative.md](runbooks/review-delivery-initiative.md)

The PM² phase field is only trustworthy when it also carries governed
transition semantics.

Supported meaning:

- `Initiating`
  - initiative shell exists and intake-to-delivery admission is still being established
- `Planning`
  - initiative framing and PI commitment are still being shaped
- `Executing`
  - committed delivery work is still active beneath the initiative
- `Closing`
  - implementation work is execution-complete enough for formal closeout review

`Closing` is not just a visual bucket. It now has entry criteria.

The initiative may enter `Closing` only when:

- `System Demo Evidence` is recorded on the top-level `Epic`
- the execution tree has no descendants outside `done` or `retired`
- no blocked items remain
- no unresolved dependency relations remain
- no done descendants are missing completion evidence
- no done descendants still have weak completion evidence
- no done descendants still have weak done-state narrative evidence
- no done descendants are missing `Owner Repo`, `Assignee`, or `Responsible`

The initiative may move to final `done` only when:

- `PM² Phase = Closing`
- `System Demo Evidence` is still present
- `Inspect & Adapt Actions` is recorded
- the final closeout-readiness summary is still clean

The initiative may move to terminal `retired` only when:

- all descendants are already `done` or `retired`
- no open child scope is left behind under the retired initiative
- the operator uses the initiative governance route rather than treating
  retirement as a PM² phase change
- the stored `PM² Phase` value is cleared as part of the retirement transition

That means the PM² board and the closeout workflow now line up:

- `Closing` means formal initiative closeout review is under way
- `done` means the initiative-review evidence and execution closeout are both complete
- `retired` means the initiative ended without successful closeout and now lives
  in the separate retired terminal lane on the PM² board

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

The managed `PM² Phase Board` is therefore:

- `Initiating`
- `Planning`
- `Executing`
- `Closing`
- `Retired`

The first four lanes are PM² phases. `Retired` is a separate terminal
initiative-status lane.

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

Primary operator surface:

- `products/openproject/runbooks/manage-delivery-blockers.md`

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

Trigger a blocker when the exact next committed ART step cannot proceed because
of:

- a live mutation, closeout, or review failure that the same proof cycle did
  not clear
- a repeated failure on the same active step
- a missing required principal, approval, PI commitment, iteration, runtime,
  or environment prerequisite
- an unresolved dependency
- a security or governance hold
- a quality or readiness gate preventing the transition

Once the blocker is known:

- stop adjacent ART mutation on the same initiative
- record the blocker on the affected work item
- open or update a real `Defect` when the blocker is caused by a live system or
  workflow control bug
- open or update a `Risk` when the exposure is broader than one blocked item

Do not treat `blocked` as something generic create, update, or planning-repair
surfaces can set directly. Enter and clear `blocked` through the dedicated
blocker workflow so the blocker fields, decision path, and follow-up posture
stay bounded and reviewable.

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
