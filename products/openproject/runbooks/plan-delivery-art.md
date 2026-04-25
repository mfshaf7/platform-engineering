# Plan Delivery ART

## Purpose

Define the only supported planning workflow for new work that has already been
accepted and is entering `Workspace Delivery ART`.

Use this runbook to keep consume, initiative framing, PI commitment,
rolling-wave elaboration, and carryover review aligned to one machine-enforced
model.

Canonical planning-workflow contract:

- [delivery-art-planning-workflow.json](../delivery-art-planning-workflow.json)

That file is the machine-readable source for:

- phase order
- allowed item creation by phase
- required fields by phase
- forbidden actions by phase
- control-gate ids and whether they are machine-enforced or operator-enforced

Use this runbook as the primary operator surface. Use the JSON contract when
validation, broker, or cross-repo drift checks need the exact gate metadata.

## Exact Checklist Matrix

### 1. Consume

Operator checklist:

- create one `Epic` shell only
- set:
  - `Owner Repo`
  - `PM² Phase`
- allow `Target PI` to stay blank when the initiative is not yet committed
- verify the initiative projects into `Not yet committed to a PI`

Forbidden:

- creating `PI Objective`, `User story`, `Task`, or `Milestone` work during
  consume
- creating top-level delivery work through the generic work-item create surface

Controls:

- `consume-top-level-shell-only`
- `consume-must-use-proposal-handoff`

### 2. Initiative Framing

Operator checklist:

- keep backlog children to:
  - `Feature`
  - `Risk`
  - backlog `Defect` only when it is truly held as correction work
- keep backlog work in `new`
- keep backlog `Feature` items umbrella-shaped

Forbidden:

- story forests under backlog `Feature` items
- active non-`Epic` backlog work without PI commitment

Controls:

- `backlog-feature-must-stay-umbrella-shaped`
- `active-non-epic-must-not-stay-uncommitted`

### 3. PI Planning

Operator checklist:

- create or update:
  - `PI Objective`
  - committed `Feature`
  - committed `Risk`
  - committed `Defect` only when it truly belongs in the PI slice
- set for committed non-`Epic` work:
  - `Target PI`
  - non-backlog `Iteration`
  - `Owner Repo`
  - `Assignee`
  - `Responsible`

Forbidden:

- leaving committed work on the backlog iteration label
- using roadmap `version` as if it were the canonical planning field
- PI-committing initiative scope without at least one `PI Objective`

Controls:

- `pi-committed-initiative-must-have-pi-objective`
- `target-pi-required-on-committed-leaf-types`
- `committed-non-epic-must-carry-non-backlog-iteration`
- `roadmap-version-must-match-target-pi-projection`

### 4. Rolling-Wave Elaboration

Operator checklist:

- create `User story` work only for committed `Feature` items
- create `Task` work only under active `User story` or `Defect` items
- keep new elaboration inside the already committed slice
- make sure each PI-committed `Feature` already has at least one open
  `User story` or `Defect` child

Forbidden:

- story or task creation under uncommitted parents
- pre-expanding backlog `Feature` work into execution trees
- leaving a PI-committed `Feature` without an open `User story` or `Defect`
  child

Controls:

- `pi-committed-feature-must-have-open-leaf-child`
- `story-and-task-parent-must-be-committed`
- `target-pi-required-on-committed-leaf-types`
- `committed-non-epic-must-carry-non-backlog-iteration`

### 5. Execution

Operator checklist:

- use continuation context to identify the actual leaf front
- update execution status on the story, defect, or task that is really active
- leave umbrella `Feature` or `PI Objective` items as planning/context shells
  when child work is still open

Forbidden:

- treating a ready umbrella item as executable next work without checking
  continuation context first
- leaving active non-`Epic` work uncommitted
- leaving an active `Feature` without an open `User story` or `Defect` child

Controls:

- `active-non-epic-must-not-stay-uncommitted`
- `pi-committed-feature-must-have-open-leaf-child`
- `execute-from-leaf-front`

### 6. Review, Carryover, and Decommit

Operator checklist:

- record PI review on each reviewed `PI Objective`
- close done work with evidence
- re-target true carryover to the next PI
- move decommitted open work back to backlog posture explicitly

Forbidden:

- leaving open work pointed at a PI it is no longer committed to
- treating PI review as complete without review outcome and actual business
  value

Controls:

- `pi-review-must-carry-review-outcome-and-actual-value`
- `carryover-must-be-retargeted-or-decommitted`

## Control Gate Matrix

| Gate ID | Type | What It Enforces | Primary Surface |
| --- | --- | --- | --- |
| `consume-top-level-shell-only` | machine | consume creates one top-level `Epic` shell only | broker consume route |
| `consume-must-use-proposal-handoff` | machine | top-level initiatives cannot be created through generic work-item create | broker work-item create route |
| `backlog-feature-must-stay-umbrella-shaped` | machine | backlog `Feature` items cannot own `User story` children | ART quality checker |
| `pi-committed-initiative-must-have-pi-objective` | machine | initiative scope with PI-committed non-`Epic` work must include at least one `PI Objective` | ART quality checker |
| `target-pi-required-on-committed-leaf-types` | machine | `PI Objective`, `User story`, `Task`, and `Milestone` must carry `Target PI`; `Milestone` is checkpoint-only and does not replace a `PI Objective` or leaf front | broker create/update/move + ART quality checker |
| `active-non-epic-must-not-stay-uncommitted` | machine | `ready`, `in-progress`, or `blocked` non-`Epic` work must carry `Target PI` | broker create/update + ART quality checker |
| `committed-non-epic-must-carry-non-backlog-iteration` | machine | committed non-`Epic` work must carry non-backlog `Iteration` | broker create/update + ART quality checker |
| `pi-committed-feature-must-have-open-leaf-child` | machine | PI-committed `Feature` work must keep at least one open `User story` or `Defect` child | ART quality checker + broker plan/update guards |
| `story-and-task-parent-must-be-committed` | machine | story and task work may only live beneath PI-committed parents | broker create/move |
| `roadmap-version-must-match-target-pi-projection` | machine | roadmap `version` stays a faithful projection of canonical `Target PI` | roadmap healer + ART quality checker |
| `execute-from-leaf-front` | operator | operators verify continuation context before treating umbrella work as the next front | broker continuation-context + ART skill |
| `pi-review-must-carry-review-outcome-and-actual-value` | machine | reviewed PI objectives must record review outcome and actual value | broker PI-review route |
| `carryover-must-be-retargeted-or-decommitted` | operator | open work at PI review must be re-targeted or decommitted explicitly | PI review checklist + ART planning read |

## Workflow

### 1. Consume

Start from the accepted proposal and create one `Epic` shell in
`Workspace Delivery ART`.

Rules:

- consume creates the top-level initiative only
- do not create PI objectives, user stories, tasks, or other deep execution
  trees during consume
- `Target PI` may stay blank at this stage
- the roadmap projection should place backlog work in
  `Not yet committed to a PI`
- retired blank-`Target PI` scope belongs in `Retired scope`, not the backlog
  bucket

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

Rules:

- do not PI-commit initiative scope unless at least one `PI Objective` exists
  in the same initiative

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
- once a `Feature` carries `Target PI` and a non-backlog `Iteration`, it must
  already have at least one open `User story` or `Defect` child

### 5. Execution

Execute from the leaf work, not the umbrella shell.

Rules:

- the executable front is the child `User story`, `Defect`, or `Task`
- a `Feature` or `PI Objective` can stay `ready` or `in-progress`, but it is
  not the actionable next item when it still has open child work
- use continuation context to confirm the real next leaf instead of treating
  planning alone as sufficient proof
- if an active `Feature` has no open `User story` or `Defect` child, repair
  the planning tree before presenting it as executable work

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
  - once it carries `Target PI` and a non-backlog `Iteration`, it must keep at
    least one open `User story` or `Defect` child
- `Risk`
  - may exist without `Target PI`
- `Defect`
  - may exist without `Target PI` only while it remains backlog correction work
    in `new` posture
- `PI Objective`
  - must always carry `Target PI`
  - at least one `PI Objective` must exist before an initiative can keep
    PI-committed non-`Epic` scope
- `User story`
  - must always carry `Target PI`
- `Task`
  - must always carry `Target PI`
- `Milestone`
  - must always carry `Target PI`
  - remains an `Epic`-level checkpoint, not an execution container
  - does not replace a `PI Objective`
  - does not satisfy the `Feature` leaf-front requirement

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
- PI-committed initiative scope without a `PI Objective`
- PI-committed `Feature` work without an open `User story` or `Defect` child
- PI-committed non-`Epic` work without `Iteration`
- roadmap drift between canonical `Target PI` and derived `version`
- active non-`Epic` work that still looks uncommitted

## Related References

- [delivery-art-contract.md](../delivery-art-contract.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [standardize-delivery-art.md](standardize-delivery-art.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
