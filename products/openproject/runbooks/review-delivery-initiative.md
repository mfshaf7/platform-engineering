# Review Delivery Initiative

## Purpose

Define the only supported PM² initiative-review and closeout workflow for
top-level `Epic` initiatives inside `Workspace Delivery ART`.

Use this runbook when an initiative is approaching completion and the operator
needs to:

- record the system demo
- move the initiative into `Closing`
- record inspect-and-adapt actions
- mark the initiative `done`
- or retire the initiative cleanly without pretending it completed successfully

Canonical machine-readable workflow contract:

- [delivery-art-initiative-review-workflow.json](../delivery-art-initiative-review-workflow.json)

Use this runbook as the primary operator surface. Use the JSON contract when
validation, broker, or cross-repo checks need the exact gate metadata.

## Exact Checklist Matrix

### 1. Record System Demo

Operator checklist:

- record `System Demo Evidence` on the top-level `Epic`
- include:
  - date
  - outcome
  - summary
  - evidence
  - follow-up when needed
- treat this as initiative-level evidence, not child work-item completion proof

Forbidden:

- moving the initiative to `Closing` before any system-demo entry exists
- treating work-item completion evidence as a substitute for initiative system-demo evidence

Controls:

- `initiative-closing-requires-system-demo`

### 2. Enter PM² Closing

Operator checklist:

- move `PM² Phase` on the initiative `Epic` from `Executing` to `Closing`
- verify the execution tree is already clean for formal closeout review:
  - no open descendants outside `done` or `retired`
  - no blocked items
  - no unresolved dependency relations
  - no done descendants missing or weakening completion evidence
  - no done descendants with weak done-state narrative evidence
  - no done descendants missing ownership fields

Forbidden:

- entering `Closing` while active delivery work is still open
- entering `Closing` without recorded system-demo evidence

Controls:

- `initiative-closing-requires-system-demo`
- `initiative-closing-requires-clean-execution-state`

### 3. Record Inspect And Adapt

Operator checklist:

- record `Inspect & Adapt Actions` on the top-level `Epic`
- include:
  - review date
  - summary
  - action items
  - follow-up when needed

Forbidden:

- marking the initiative `done` without any inspect-and-adapt record

Controls:

- `initiative-done-requires-inspect-and-adapt`

### 4. Mark Initiative Done

Operator checklist:

- keep `PM² Phase = Closing`
- mark the initiative status `done` only after:
  - system demo is recorded
  - inspect-and-adapt is recorded
  - final closeout readiness is still clean

Forbidden:

- `done` while `PM² Phase` is still `Initiating`, `Planning`, or `Executing`
- `done` with missing initiative-review evidence
- `done` while execution closeout readiness is still dirty

Controls:

- `initiative-done-requires-closing-phase`
- `initiative-done-requires-system-demo`
- `initiative-done-requires-inspect-and-adapt`
- `initiative-done-requires-final-closeout-readiness`

### 5. Retire Initiative

Operator checklist:

- use the initiative governance route to set initiative status to `retired`
- clear `PM² Phase` as part of the retirement update
- first verify every descendant is already terminal:
  - `done`, or
  - `retired`
- retire or otherwise dispose of child scope before retiring the top-level `Epic`

Forbidden:

- treating `retired` as a PM² phase
- leaving a stale `PM² Phase` value on a retired initiative
- retiring an initiative while it still has open descendants
- using initiative retirement to hide incomplete active child work

Controls:

- `initiative-retired-requires-terminal-descendants`
- `initiative-retired-clears-pm2-phase`

## Control Gate Matrix

| Gate ID | Type | What It Enforces | Primary Surface |
| --- | --- | --- | --- |
| `initiative-closing-requires-system-demo` | machine | `Closing` requires recorded `System Demo Evidence` | broker initiative governance + system-demo route |
| `initiative-closing-requires-clean-execution-state` | machine | `Closing` requires a clean execution tree and clean descendant closeout state | broker initiative governance + ART quality checker |
| `initiative-done-requires-closing-phase` | machine | done initiatives must remain in PM² `Closing` | broker initiative governance + ART quality checker |
| `initiative-done-requires-system-demo` | machine | done initiatives must retain `System Demo Evidence` | broker initiative governance + ART quality checker |
| `initiative-done-requires-inspect-and-adapt` | machine | done initiatives must retain `Inspect & Adapt Actions` | broker initiative governance + ART quality checker |
| `initiative-done-requires-final-closeout-readiness` | machine | done initiatives must still satisfy final closeout readiness | broker initiative governance + ART quality checker |

## Workflow

### 1. System Demo

Use the broker initiative-review route to append system-demo evidence to the
top-level initiative:

- `POST /v1/delivery-initiatives/{delivery_id}/system-demo`

This evidence belongs on the initiative because it proves the delivered slice
was demonstrated at the initiative review layer. It is not a substitute for
child completion evidence.

### 2. Closing Review Entry

Before moving the initiative into `Closing`, run the execution summary and
closeout-readiness reads:

- `GET /v1/delivery-initiatives/{delivery_id}/execution-summary`
- `GET /v1/delivery-initiatives/{delivery_id}/closeout-readiness`

Only enter `Closing` when the initiative is execution-complete enough for
formal closeout review.

### 3. Inspect And Adapt

Use:

- `POST /v1/delivery-initiatives/{delivery_id}/inspect-and-adapt`

This records initiative-level review outcomes and the follow-on actions that
survive after the implementation tree itself is already closed.

### 4. Final Done Transition

Use:

- `POST /v1/delivery-initiatives/{delivery_id}/governance`

with:

- `pm2_phase = Closing`
- `status = done`

The initiative should fail closed if system-demo evidence, inspect-and-adapt,
or final closeout readiness is missing.

### 5. Retire Initiative

Use:

- `POST /v1/delivery-initiatives/{delivery_id}/governance`

with:

- `status = retired`

Retirement is the non-success terminal path. It does not require `Closing`,
system-demo evidence, or inspect-and-adapt evidence, but it must not leave any
descendants outside `done` or `retired`. The retirement transition also clears
the stored `PM² Phase` value so the retired lane does not keep a stale active
phase label.

## Retrospective Backfill Rule

Older initiatives that predate this governed review workflow may be backfilled,
but only explicitly and honestly.

When backfilling:

- keep the initiative in `done`
- set `PM² Phase = Closing`
- add clearly retrospective entries to:
  - `System Demo Evidence`
  - `Inspect & Adapt Actions`
- make the entry text explicit that the review is retrospective governance
  backfill rather than a contemporaneous demo or inspect-and-adapt session

Do not silently rewrite history. If contemporaneous review evidence did not
exist before this workflow, say so in the retrospective record.

## Validation

Run from `platform-engineering/`:

```bash
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=<namespace> \
  TARGET_EPIC_ID=<epic-id> \
  INCLUDE_DONE=true
```

The quality report should come back clean before the initiative is treated as
truthfully closed on the PM² board.

## Related References

- [delivery-art-contract.md](../delivery-art-contract.md)
- [plan-delivery-art.md](plan-delivery-art.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
