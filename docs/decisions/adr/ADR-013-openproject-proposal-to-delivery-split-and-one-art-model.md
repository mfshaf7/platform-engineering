# ADR-013: OpenProject Proposal-To-Delivery Split And One-ART Model

## Status

- Accepted

## Context

The workspace now has a real proposal intake plane in OpenProject:

- `Workspace Proposals`

That plane is appropriate for:

- raw ideas
- operator-authored triage
- bounded durable proposal decisions such as `parked`, `accepted`, and
  `rejected`

It is not the right execution plane for enterprise delivery work.

The next workflow goal is to consume accepted ideas into a real project
management system that can demonstrate enterprise delivery governance and
execution in OpenProject itself.

The design must support:

- enterprise-grade governance rather than an ad hoc task board
- a credible scaled-agile story for demonstration purposes
- continued separation between proposal records and delivery records
- a clean intake point from `Workspace Proposals`
- a path that can be exercised first in `dev-integration`

## Decision

Use the same OpenProject runtime but split proposal and delivery into separate
logical projects.

The chosen model is:

- `Workspace Proposals` remains the intake and proposal backlog
- a separate OpenProject delivery project represents one `Agile Release Train`
- accepted ideas are explicitly consumed from the proposal backlog into the
  delivery project
- the proposal record remains the proposal-of-record
- the delivery record becomes the execution-of-record

Use `PM²` as the formal enterprise governance model and use a SAFe-aligned
one-ART structure for execution inside the delivery project.

Specifically:

- PM² governs the top-level consumed initiative
- the delivery project models one ART
- Versions model Program Increments
- work package hierarchy models:
  - `Epic`
  - `Feature`
  - `Enabler`
  - `User story`
  - `Task`
  - `Milestone`
- Kanban boards visualize execution within that ART

The intake boundary is:

- source idea reaches `accepted` in `Workspace Proposals`
- an explicit consume step creates a linked delivery record in the ART project

The first target shape is one ART only.

Multiple ARTs and solution-train style coordination are deferred until the
single-ART model is coherent and demonstrably useful.

## Consequences

What becomes simpler:

- proposal lifecycle stays distinct from delivery lifecycle
- enterprise governance can be demonstrated without overloading the intake
  backlog
- SAFe alignment can be shown through ART, PI, hierarchy, and Kanban views
  without pretending every proposal record is already execution work
- one ART gives a credible scaled-agile story without artificial early
  multi-train complexity

What becomes harder:

- the workspace must manage two linked OpenProject planes instead of one
- proposal-to-delivery consumption needs explicit link, field mapping, and
  eventual automation
- OpenProject project, type, workflow, and board configuration becomes richer
  than the current proposal-only backlog model

Required follow-up work:

- define the OpenProject delivery project contract for the one-ART model
- define the broker-side accepted-idea consumption contract
- add a proposed `dev-integration` profile for local rehearsal of accepted-idea
  consumption into the ART delivery project
- later implement the consume step first in `dev-integration`, then route the
  winning shape through the normal PR and stage path

Governed rollout evidence is still deferred. If this ADR is later implemented
in a governed environment, the rollout must be captured through the appropriate
change records.

## Alternatives Considered

- Keep `Workspace Proposals` as both intake and execution project
  - Not chosen because it collapses proposal and delivery semantics into one
    plane and weakens the enterprise demonstration
- Use plain Kanban without PM²
  - Not chosen because the target is an enterprise-grade demonstration, not
    just an operational task board
- Start with multiple ARTs immediately
  - Not chosen because it increases configuration and storytelling complexity
    before the single-ART model is proven
