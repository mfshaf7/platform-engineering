# Manage Delivery Parking

## Purpose

Park or resume a delivery work item through the supported OpenProject operator
surface instead of deleting the item or leaving it as silent active scope.

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

Parking sets status to `parked` and clears active blocker fields so parked
items do not keep poisoning closeout readiness or active execution views.

## Park A Work Item

```bash
make openproject-manage-delivery-parking \
  TARGET_WORK_PACKAGE_ID=43 \
  ACTION=park \
  PARK_DECISION=retire \
  PARK_REASON="This task was created during planning, but the move surface now covers the correction directly." \
  WORK_NOTE="Parked after the hierarchy correction was proven through the dedicated move helper."
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

- sets delivery status to `parked`
- writes the parking governance fields
- requires `PARK_REVIEW_DATE` when `PARK_DECISION=defer`
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
- refuses `RESUME_STATUS=parked`

## Dev-Integration Lane

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-manage-delivery-parking \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_WORK_PACKAGE_ID=43 \
  ACTION=park \
  PARK_DECISION=retire \
  PARK_REASON="..."
```

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target work package
- confirm the work package status is `parked` after `ACTION=park`
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
