# Update Delivery Work Item

## Purpose

Update one delivery work item inside `Workspace Delivery ART` through the
supported operator surface instead of piecemeal UI edits or ad hoc Rails
commands.

Use this for day-to-day execution changes below the top-level initiative, such
as:

- moving a work item to a new execution status
- assigning or clearing a concrete owner
- setting or clearing `Target PI`
- updating SAFe execution metadata such as team, iteration, acceptance criteria,
  PI-objective values, risk data, or WSJF inputs
- updating or clearing the work-item description
- adding an operator work note for the change

Do not use this workflow to mark a work item `done`.

Completed work must go through
[complete-delivery-work-item.md](complete-delivery-work-item.md) so the record
captures explicit completion evidence instead of only a status change.

Use [update-delivery-initiative.md](update-delivery-initiative.md) for the
top-level `Epic` PM² governance fields.
Use [create-delivery-work-item.md](create-delivery-work-item.md) when the
target child item does not exist yet.

## Command

Run from `platform-engineering/`:

```bash
make openproject-update-delivery-work-item \
  TARGET_WORK_PACKAGE_ID=40 \
  STATUS=in-progress \
  ASSIGNEE_LOGIN=admin \
  TARGET_PI=PI-2026-02 \
  START_DATE=2026-04-21 \
  DUE_DATE=2026-04-25 \
  ESTIMATED_WORK=8 \
  REMAINING_WORK=5 \
  PERCENT_COMPLETE=40 \
  DELIVERY_TEAM="Platform Architecture" \
  ITERATION="Iteration 1" \
  ACCEPTANCE_CRITERIA="- Engine vs instance inventory is captured in a committed source artifact." \
  DESCRIPTION="Execution inventory is now underway for the control-plane split." \
  WORK_NOTE="Started active execution after planning discussion closed."
```

Optional fields:

- `STATUS`
- `TARGET_PI`
- `CLEAR_TARGET_PI=true`
- `ASSIGNEE_LOGIN`
- `CLEAR_ASSIGNEE=true`
- `DESCRIPTION`
- `CLEAR_DESCRIPTION=true`
- `WORK_NOTE`
- `START_DATE`
- `CLEAR_START_DATE=true`
- `DUE_DATE`
- `CLEAR_DUE_DATE=true`
- `ESTIMATED_WORK`
- `CLEAR_ESTIMATED_WORK=true`
- `REMAINING_WORK`
- `CLEAR_REMAINING_WORK=true`
- `PERCENT_COMPLETE`
- `DELIVERY_TEAM`
- `ITERATION`
- `ACCEPTANCE_CRITERIA`
- `DEFINITION_OF_READY`
- `DEFINITION_OF_DONE`
- `NFR_CATEGORY`
- `PI_OBJECTIVE_TYPE`
- `PLANNED_BUSINESS_VALUE`
- `ACTUAL_BUSINESS_VALUE`
- `ROAM_STATE`
- `RISK_OWNER`
- `RISK_REVIEW_DATE`
- `RISK_DISPOSITION`
- `WSJF_USER_BUSINESS_VALUE`
- `WSJF_TIME_CRITICALITY`
- `WSJF_RR_OE`
- `WSJF_JOB_SIZE`

Restriction:

- `STATUS=done` is intentionally rejected here
- use [complete-delivery-work-item.md](complete-delivery-work-item.md) for completion
  with evidence

Rules:

- `TARGET_PI` and `CLEAR_TARGET_PI=true` are mutually exclusive
- `ASSIGNEE_LOGIN` and `CLEAR_ASSIGNEE=true` are mutually exclusive
- `CLEAR_DESCRIPTION=true` removes the current description
- `CLEAR_START_DATE=true`, `CLEAR_DUE_DATE=true`, `CLEAR_ESTIMATED_WORK=true`,
  and `CLEAR_REMAINING_WORK=true` remove those values
- `WORK_NOTE` adds one operator note during the save
  - if the runtime exposes journal notes through this path, the note is written there
  - otherwise the note is appended to an `Operator work notes` section in the description
- structured SAFe fields are validated against the target work-item type
- `STATUS=ready` is rejected when the required structured execution fields for
  the target type are still missing
- `WSJF Score` is recomputed automatically when any WSJF component field changes
- end-of-PI review outcome is intentionally recorded through
  [record-pi-review.md](record-pi-review.md), not through this generic execution
  update surface

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-update-delivery-work-item \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_WORK_PACKAGE_ID=40 \
  STATUS=in-progress \
  ASSIGNEE_LOGIN=admin
```

## Expected Outcome

- the target work item reflects the requested execution changes
- schedule and progress values are updated through the same supported path
- `Program Increment Planning` stays in sync when `TARGET_PI` is supplied
- the command prints the updated work-item state plus the fields that actually changed
- the command also reports where `WORK_NOTE` was applied

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target work item
- confirm the intended `Status`, `Target PI`, `Assignee`, and description values
- confirm any supplied schedule and progress values reflect the intended state
- confirm any supplied structured SAFe fields reflect the intended values
- if `WORK_NOTE` was supplied, confirm the note appears either in the activity history or in the `Operator work notes` description section

## Related References

- [start-delivery-execution.md](start-delivery-execution.md)
- [update-delivery-initiative.md](update-delivery-initiative.md)
- [create-delivery-work-item.md](create-delivery-work-item.md)
- [move-delivery-work-item.md](move-delivery-work-item.md)
- [complete-delivery-work-item.md](complete-delivery-work-item.md)
- [record-pi-review.md](record-pi-review.md)
- [manage-delivery-dependency.md](manage-delivery-dependency.md)
- [manage-delivery-blocker.md](manage-delivery-blocker.md)
- [close-delivery-initiative.md](close-delivery-initiative.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
