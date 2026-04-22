# Manage Delivery Parking

## Purpose

Park or resume a delivery work item through the supported OpenProject operator
surface instead of deleting the item or leaving it as silent active scope.

This command is broker-backed. The OpenProject product surface keeps the
operator command and runbook, but the inactive-scope workflow executes through
the internal broker route:

- `POST /v1/delivery-work-items/{work_item_id}/parking`

Use this when a delivery item is:

- no longer needed
- deferred to a later planning cycle
- superseded by a better execution shape
- mistaken scope that should stop cluttering active execution views

## Current Truth

For delivery work, removing an item from active scope must still be auditable.

The operator surface must capture:

- `Parking Decision`
  - `defer`
  - `retire`
- `Parking Reason`
- `Parking Review Date` when the decision is `defer`
- `Retirement Reason` when the decision is `retire`
  - `superseded`
  - `duplicate`
  - `invalid`
  - `absorbed`
  - `cancelled`

Deferred items move to status `parked`. Retired items move to status
`retired`. Both paths clear active blocker fields so deferred or retired items
do not keep stale blocker noise in execution views.

`parked` is deferred open work:

- it remains visible in all-open execution and portfolio views by default
- it still blocks initiative closeout
- it may return later through `ACTION=resume`

`retired` is terminal inactive work:

- it is hidden from normal open views by default
- it does not block closeout by itself

## Park A Work Item

```bash
make openproject-manage-delivery-parking \
  TARGET_WORK_PACKAGE_ID=43 \
  ACTION=park \
  PARK_DECISION=retire \
  RETIREMENT_REASON=superseded \
  PARK_REASON="This task was created during planning, but the move surface now covers the correction directly." \
  WORK_NOTE="Retired after the hierarchy correction was proven through the dedicated move helper."
```

For a deferred item:

```bash
make openproject-manage-delivery-parking \
  TARGET_WORK_PACKAGE_ID=43 \
  ACTION=park \
  PARK_DECISION=defer \
  PARK_REASON="Keep this work item out of active scope until PI-2026-03 planning starts." \
  PARK_REVIEW_DATE=2026-05-01
```

Behavior:

- sets delivery status to `parked` for `PARK_DECISION=defer`
- sets delivery status to `retired` for `PARK_DECISION=retire`
- writes the parking governance fields
- requires `PARK_REVIEW_DATE` when `PARK_DECISION=defer`
- requires `RETIREMENT_REASON` when `PARK_DECISION=retire`
- clears any blocker governance fields on the same item

## Resume A Parked Work Item

```bash
make openproject-manage-delivery-parking \
  TARGET_WORK_PACKAGE_ID=43 \
  ACTION=resume \
  RESUME_STATUS=ready \
  WORK_NOTE="Returned to active scope after the next planning pass reopened the task."
```

Behavior:

- clears the parking governance fields
- moves the work item to `RESUME_STATUS`
- refuses `RESUME_STATUS=parked` or `RESUME_STATUS=retired`

## Dev-Integration Lane

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-manage-delivery-parking \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_WORK_PACKAGE_ID=43 \
  ACTION=park \
  PARK_DECISION=retire \
  RETIREMENT_REASON=superseded \
  PARK_REASON="..."
```

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target work package
- confirm the work package status is `parked` after `ACTION=park PARK_DECISION=defer`
- confirm the work package status is `retired` after `ACTION=park PARK_DECISION=retire`
- confirm the parking fields are populated
- confirm blocker fields are cleared if the item was previously blocked
- after `ACTION=resume`, confirm the parking fields are empty and the status
  has moved to `RESUME_STATUS`

## Related References

- [create-delivery-work-item.md](create-delivery-work-item.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [check-delivery-closeout-readiness.md](check-delivery-closeout-readiness.md)
- [delivery-art-contract.md](../delivery-art-contract.md)

## Backend Boundary

Ownership split:

- broker route, request validation, audit, and OpenProject parking adapter:
  `operator-orchestration-service`
- operator command and OpenProject runbook surface:
  `platform-engineering`
