# Create Delivery Work Item

## Purpose

Create one new child delivery work item under an existing parent without
rebuilding a whole JSON delivery plan.

Use this when:

- the delivery tree already exists
- you want to decompose incrementally during execution
- you need one new `PI Objective`, `Feature`, `Enabler`, `User story`, `Task`,
  `Milestone`, or `Risk`
- a full plan reapply would be unnecessary overhead

Use [start-delivery-execution.md](start-delivery-execution.md) when you are
seeding the first execution tree from a plan file. Use
[update-delivery-work-item.md](update-delivery-work-item.md) when the target
item already exists.

## Command

Run from `platform-engineering/`:

```bash
make openproject-create-delivery-work-item \
  PARENT_WORK_PACKAGE_ID=39 \
  TYPE=Task \
  SUBJECT="Inventory repo split boundary" \
  STATUS=ready \
  TARGET_PI=PI-2026-02 \
  START_DATE=2026-04-21 \
  DUE_DATE=2026-04-25 \
  ESTIMATED_WORK=8 \
  REMAINING_WORK=8 \
  PERCENT_COMPLETE=0 \
  DELIVERY_TEAM="Platform Architecture" \
  ITERATION="Iteration 1" \
  ACCEPTANCE_CRITERIA="- Engine and instance boundaries are enumerated in source-backed evidence." \
  DESCRIPTION="Document which current governance pieces become reusable product code versus tenant-local instance data."
```

Required fields:

- `PARENT_WORK_PACKAGE_ID`
- `TYPE`
- `SUBJECT`

Optional fields:

- `STATUS`
- `TARGET_PI`
- `ASSIGNEE_LOGIN`
- `DESCRIPTION`
- `START_DATE`
- `DUE_DATE`
- `ESTIMATED_WORK`
- `REMAINING_WORK`
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

Behavior:

- creates exactly one new child item under the requested parent
- sends the create request through the broker-owned internal delivery API
- when `ASSIGNEE_LOGIN` is supplied, it must be a login that OpenProject
  exposes as assignable in the target project
- fails if a sibling already exists with the same `parent + type + subject`
- inherits the parent priority
- inherits the parent PI when `TARGET_PI` is not supplied
- writes `Target PI` as the delivery PI placement field
- supports initial schedule and progress fields directly on creation
- validates that structured SAFe fields are applicable to the requested type
- rejects `STATUS=ready` when the required structured execution fields for the
  requested type are still missing
- computes `WSJF Score` automatically when the WSJF component fields are supplied
- refreshes delivery-art views when `TARGET_PI` is supplied

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-create-delivery-work-item \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  PARENT_WORK_PACKAGE_ID=39 \
  TYPE=Task \
  SUBJECT="Inventory repo split boundary"
```

## Expected Outcome

- the new child work item exists under the requested parent
- the command prints the created work-item state
- `Program Increment Planning` stays in sync when `TARGET_PI` is supplied

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the parent work item
- confirm the new child item exists under the correct parent
- confirm the intended `Status` and `Target PI` values
- if `ASSIGNEE_LOGIN` was supplied, confirm the chosen login is assignable in
  the project and appears on the created item
- confirm any supplied schedule and progress values are present
- confirm any supplied structured SAFe fields appear on the new record

## Related References

- [start-delivery-execution.md](start-delivery-execution.md)
- [move-delivery-work-item.md](move-delivery-work-item.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [record-pi-review.md](record-pi-review.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
