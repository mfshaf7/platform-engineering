# Manage Delivery Blockers

## Purpose

Define the only supported blocker workflow for active `Workspace Delivery ART`
work.

Use this runbook when the exact next committed step cannot proceed and the
blocked state must be represented in ART explicitly instead of living only in
chat, a board label, or a self-improvement candidate.

Canonical machine-readable blocker workflow contract:

- [delivery-art-blocker-workflow.json](../delivery-art-blocker-workflow.json)

Use this runbook as the primary operator checklist. Use the JSON contract when
validation, broker mirrors, or cross-repo drift checks need the exact gate
inventory.

## Exact Checklist Matrix

### 1. Recognize The Trigger

Record a blocker when any of these are true for the active next step:

- the exact next committed ART step cannot proceed
- a live mutation, closeout, or review action failed and the same proof cycle
  did not clear it
- the same active step failed again after an earlier corrective attempt in the
  same task or session
- a required principal, approval, PI commitment, iteration, runtime, or
  environment prerequisite is missing for committed work
- an unresolved dependency prevents the next committed step
- security or governance review is explicitly holding the step
- a quality or readiness gate prevents the transition

Forbidden:

- continuing adjacent ART mutation after the blocker is known
- leaving the blocker only in chat, only in a self-improvement candidate, or
  only in the `blocked` status label

Controls:

- `exact-blocker-must-be-recorded-before-adjacent-mutation`

### 2. Record The Blocker On The Affected Work Item

Use the bounded blocker route:

```bash
npm run art -- item blocker <work-item-id> <payload.json>
```

Required blocker fields:

- `blocker_statement`
- `blocker_impact`
- `blocker_owner`
- `blocker_discovered_on`
- `blocker_decision_path`
- `blocker_justification`

If `blocker_decision_path` is not `remove`, also record:

- `blocker_follow_up_owner`
- `blocker_review_date`

Rules:

- entering `blocked` must use the blocker workflow
- generic create, update, and planning-repair surfaces do not set blocked

Controls:

- `blocked-status-must-use-blocker-workflow`
- `blocked-status-requires-bounded-blocker-record`

### 3. Represent The Right Scope

Use the bounded blocker record for the item-local execution impediment.

Also open or update:

- a real `Defect` when the blocker is caused by a live system or workflow
  control bug
- a `Risk` when the exposure is broader than one blocked item or is expected
  to survive beyond that one item

Do not use `Risk` as a substitute for the blocked item record when the next
step is already blocked.

Controls:

- `same-step-repeat-must-open-defect-or-update-existing-one`
- `broader-art-or-pi-exposure-must-open-risk`

### 4. Work While Blocked

Allowed work while the blocker is active:

- blocker diagnosis and unblock proof
- the smallest faithful regression or validation needed to prove the fix
- recording the linked `Defect` or `Risk`
- executing the approved `workaround`, `accept-risk`, or `defer` decision path

Forbidden:

- closing siblings, parent items, or the initiative as if the blocker were not
  active
- continuing unrelated adjacent mutation on the same initiative while the
  blocker remains unrecorded

### 5. Clear The Blocker

Clear the blocker only through the bounded blocker route with a resume status.

Allowed `resume_status` values:

- `new`
- `ready`
- `in-progress`

Use other governed workflows instead when the blocked item should become:

- `done`
  - item completion workflow
- `parked`
  - parking workflow
- `retired`
  - parking or initiative governance workflow

Rules:

- active blocker fields must not remain on an item whose status is no longer
  blocked
- generic update does not clear blocker state

Controls:

- `active-blocker-record-must-stay-on-blocked-item`
- `blocker-clear-must-use-active-resume-status`

## Related References

- [delivery-art-contract.md](../delivery-art-contract.md)
- [plan-delivery-art.md](plan-delivery-art.md)
- [review-delivery-initiative.md](review-delivery-initiative.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
