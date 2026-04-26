# Start Delivery Initiative

## Purpose

Define the first operator decision flow for accepted work entering
`Workspace Delivery ART`.

Use this runbook before the detailed planning checklist when the question is:

- should this accepted idea enter ART at all
- is it a new initiative or in-scope follow-on work
- what is the smallest correct starting shape
- when do lineage, PI commitment, and executable leaf-front rules begin

This is the primary start-here surface for accepted work entering ART.

Detailed follow-on references:

- [plan-delivery-art.md](plan-delivery-art.md)
- [manage-delivery-initiative-lineage.md](manage-delivery-initiative-lineage.md)
- [../delivery-art-contract.md](../delivery-art-contract.md)

## Decision Tree

### 1. Is the work already covered by an active initiative?

If yes:

- do not create a new top-level `Epic`
- add the smallest in-scope child work under the active initiative
- use `Feature`, `User story`, `Defect`, or `Task` according to the current
  planning phase

If no:

- continue to Step 2

### 2. Has the idea already been accepted for delivery?

If no:

- do not enter ART yet
- keep it in `Workspace Proposals`

If yes:

- create one top-level `Epic` shell only
- set:
  - `Owner Repo`
  - `PM² Phase = Initiating`

Do not create `PI Objective`, `User story`, `Task`, or `Milestone` work during
consume.

### 3. Is the new epic still in shell posture?

The only allowed unclassified shell posture is:

- `status = new`
- `PM² Phase = Initiating`
- blank `Target PI`
- blank lineage fields

If the initiative is staying there temporarily, stop here.

If the initiative is about to move into planning, PI commitment, retirement, or
completion, continue to Step 4.

### 4. Is this a new initiative family or a continuation of an existing one?

If it is a new top-level architecture or control thread:

- set `Initiative Family`
- set `Lineage Role = architecture-anchor`
- do not set `Architecture Anchor Ref`
- do not set `Required Upstream Ref`

If it continues an existing family:

- set `Initiative Family`
- set `Lineage Role`
- set `Architecture Anchor Ref` when the role requires it
- set `Required Upstream Ref` when the role requires it

Use [manage-delivery-initiative-lineage.md](manage-delivery-initiative-lineage.md)
for the exact family and role rules.

### 5. Are you still framing backlog scope, or are you committing PI work?

If you are still framing backlog scope:

- keep children at:
  - `Feature`
  - `Risk`
  - backlog `Defect` only when it is truly correction work
- keep backlog `Feature` items umbrella-shaped
- keep backlog work in `new`

If you are PI-committing work:

- create at least one `PI Objective`
- set committed non-`Epic` work with:
  - `Target PI`
  - non-backlog `Iteration`
  - `Owner Repo`
  - `Assignee`
  - `Responsible`

### 6. Are committed features ready to execute?

If a `Feature` is still backlog scope:

- it may remain umbrella-only

If a `Feature` is PI-committed or active:

- it must already have at least one open `User story` or `Defect` child
- do not execute directly from the umbrella `Feature`

### 7. Are you creating tasks?

Only create `Task` work when:

- the parent is an active `User story` or `Defect`

Do not create `Task` work:

- directly under `Epic`
- directly under `Feature`
- as a substitute for missing story decomposition

### 8. Do you need a milestone?

`Milestone` is optional.

Use it only when there is a real initiative-level checkpoint or exit gate.

It does not replace:

- a required `PI Objective`
- a required open `User story` or `Defect` leaf front under an active or
  PI-committed `Feature`

### 9. Are you closing the PI slice or changing commitment?

At PI review or major replanning:

- close done work with evidence
- re-target true carryover to the next PI
- decommit no-longer-committed work back to backlog posture

Do not leave open work pointing at a PI it no longer belongs to.

### 10. Are you finishing or retiring the initiative?

Successful path:

- `Initiating -> Planning -> Executing -> Closing -> done`

Non-success terminal path:

- move the initiative to `retired` only when descendants are already terminal

Do not use `retired` as a shortcut for incomplete execution.

## Minimum Valid Shapes

### Brand-New Accepted Work

- `Epic`

### Framed Backlog Initiative

- `Epic`
- optional backlog `Feature`
- optional `Risk`
- optional backlog `Defect`

### PI-Committed Initiative

- `Epic`
- `PI Objective`
- committed `Feature`

### Executable Committed Slice

- `Epic`
- `PI Objective`
- committed `Feature`
- open `User story` or `Defect`
- optional `Task` under that leaf item

## Quick Rules

- new accepted work enters ART as one `Epic` shell only
- top-level lineage may stay blank only in the temporary shell posture
- a PI-committed initiative must have a `PI Objective`
- a backlog `Feature` may stay umbrella-only
- an active or PI-committed `Feature` must have an open `User story` or
  `Defect` child
- `Task` belongs only under active `User story` or `Defect`
- `Milestone` is optional and checkpoint-only
- roadmap `version` is projection truth, not planning truth

## Next Reads

- [plan-delivery-art.md](plan-delivery-art.md) for the detailed gate matrix
- [manage-delivery-initiative-lineage.md](manage-delivery-initiative-lineage.md)
  for family and anchor rules
- [review-delivery-initiative.md](review-delivery-initiative.md) for initiative
  closeout and PM² review
