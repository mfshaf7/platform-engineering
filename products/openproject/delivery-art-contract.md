# Delivery ART Contract

## Purpose

Define the canonical OpenProject delivery plane for work that has already been
accepted in `Workspace Proposals` and now needs enterprise execution tracking.

This contract is intentionally separate from:

- `idea-backlog-contract.md`

The proposal backlog remains the intake plane. This contract defines the
delivery plane.

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

## One-ART Shape

The first delivery implementation should model one `Agile Release Train`.

SAFe-aligned mapping in OpenProject:

- project:
  - one ART
- versions:
  - Program Increments
- work package hierarchy:
  - `Epic`
  - `Feature`
  - `Enabler`
  - `User story`
  - `Task`
  - `Milestone`
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

The PM² phase is not the same thing as Kanban execution status.

## Execution Status Model

Execution tracking should stay separate from proposal lifecycle.

Recommended initial Kanban-oriented execution statuses:

- `new`
- `ready`
- `in-progress`
- `blocked`
- `done`

These statuses apply to delivery work in the ART project, not to proposal
records in `Workspace Proposals`.

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
- source proposal may move to `superseded` if a newer accepted record replaces
  it
- delivery execution statuses must not be pushed back into proposal status

## Initial Operating Model

Phase 1 should start with explicit manual consumption, not automatic sync.

That means:

- operator approves the proposal in `Workspace Proposals`
- operator or broker creates the top-level delivery initiative explicitly
- backlinks are recorded
- execution proceeds inside the ART project

Broker-assisted creation may come later, but it should preserve the same link
and governance model.

## Deferred In Phase 1

- multiple ARTs
- solution-train views
- automatic bidirectional synchronization
- direct Telegram delivery management commands
- governed stage rehearsal for this new delivery model before the concrete
  runtime shape exists
