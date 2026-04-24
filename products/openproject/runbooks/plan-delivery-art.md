# Plan Delivery ART

## Purpose

Define the only supported planning workflow for new work that has already been
accepted and is entering `Workspace Delivery ART`.

Use this runbook to keep consume, initiative framing, PI commitment,
rolling-wave elaboration, and carryover review aligned to one machine-enforced
model.

## Workflow

### 1. Consume

Start from the accepted proposal and create one `Epic` shell in
`Workspace Delivery ART`.

Rules:

- consume creates the top-level initiative only
- do not create PI objectives, user stories, tasks, or other deep execution
  trees during consume
- `Target PI` may stay blank at this stage
- the roadmap projection should place the initiative in
  `Not yet committed to a PI`

### 2. Initiative Framing

Shape the initiative while it is still backlog work.

Allowed backlog children:

- `Feature`
- `Risk`
- `Defect` only when it is explicitly being held as backlog correction work

Rules:

- backlog features stay umbrella-shaped
- backlog features must not already contain `User story` execution trees
- uncommitted work stays in `new` posture
- the initiative narrative explains scope boundaries and the current PI focus

### 3. PI Planning

Commit the near-term execution slice.

Create or update:

- `PI Objective`
- committed `Feature`
- committed `Risk`

Committed non-`Epic` work must carry:

- `Target PI`
- non-backlog `Iteration`
- `Owner Repo`
- `Assignee`
- `Responsible`

Use the roadmap as a compatibility view only. The canonical planning field is
still `Target PI`.

### 4. Rolling-Wave Elaboration

Only elaborate the committed slice.

Rules:

- create `User story` work only for committed features
- create `Task` work only under active `User story` or `Defect` items
- do not pre-expand backlog features into story forests
- if ad hoc defect work is needed before commitment, keep it explicitly in
  backlog posture until it is truly committed

### 5. Execution

Execute from the leaf work, not the umbrella shell.

Rules:

- the executable front is the child `User story`, `Defect`, or `Task`
- a `Feature` or `PI Objective` can stay `ready` or `in-progress`, but it is
  not the actionable next item when it still has open child work
- use continuation context to confirm the real next leaf instead of treating
  planning alone as sufficient proof

### 6. Review, Carryover, And Decommit

At PI review:

- close completed PI objectives and work items with evidence
- re-target genuine carryover to the next PI
- move decommitted work back to backlog posture
- do not leave stale PI placement on work that is no longer committed

## Hard Gates

Use these as the planning contract:

- `Epic`
  - may exist without `Target PI`
- `Feature`
  - may exist without `Target PI` only while it remains backlog-shaped
- `Risk`
  - may exist without `Target PI`
- `Defect`
  - may exist without `Target PI` only while it remains backlog correction work
    in `new` posture
- `PI Objective`
  - must always carry `Target PI`
- `User story`
  - must always carry `Target PI`
- `Task`
  - must always carry `Target PI`
- `Milestone`
  - must always carry `Target PI`

Committed non-`Epic` work must also carry a non-backlog `Iteration`.

## Checks

Use the ART quality gate to catch planning drift:

```bash
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=<epic-id>
```

The quality gate now fails on:

- story-level work created before PI commitment
- PI-committed non-`Epic` work without `Iteration`
- roadmap drift between canonical `Target PI` and derived `version`
- active non-`Epic` work that still looks uncommitted

## Related References

- [delivery-art-contract.md](../delivery-art-contract.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [standardize-delivery-art.md](standardize-delivery-art.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
