# Manage Delivery Blocker

## Purpose

Record or clear blocker governance on a delivery work package through the
supported OpenProject operator surface.

Use this when a delivery item becomes blocked and the blocker must be recorded
as more than a bare status flag.

This operator surface is broker-backed. The platform command remains the
primary operator entrypoint, but the actual blocker workflow runs through
`operator-orchestration-service`.

## Current Truth

For delivery work, `blocked` alone is not enough.

The operator surface must also capture:

- `Blocker Statement`
- `Blocker Impact`
- `Blocker Owner`
- `Blocker Discovered On`
- `Blocker Decision Path`
- `Blocker Justification`
- `Blocker Follow-Up Owner`
- `Blocker Review Date`

When the blocker is cleared, those fields should be removed and the work item
should move to a non-`blocked` execution status.

## Set A Blocker

```bash
make openproject-manage-delivery-blocker \
  TARGET_WORK_PACKAGE_ID=40 \
  ACTION=set \
  BLOCKER_STATEMENT="Workspace vocabulary split is not finalized yet." \
  BLOCKER_IMPACT="Engine-vs-instance inventory cannot be closed until the tenant vocabulary boundary is agreed." \
  BLOCKER_OWNER=mfshaf7 \
  BLOCKER_DISCOVERED_ON=2026-04-20 \
  BLOCKER_DECISION_PATH=workaround \
  BLOCKER_JUSTIFICATION="Proceed with the current governed vocabulary as the temporary source of truth while the product boundary is framed." \
  BLOCKER_FOLLOW_UP_OWNER=mfshaf7 \
  BLOCKER_REVIEW_DATE=2026-04-24
```

Behavior:

- sets delivery status to `blocked`
- writes the blocker governance fields
- enforces the required blocker fields
- requires `BLOCKER_FOLLOW_UP_OWNER` and `BLOCKER_REVIEW_DATE` when the
  decision path is not `remove`

## Clear A Blocker

```bash
make openproject-manage-delivery-blocker \
  TARGET_WORK_PACKAGE_ID=40 \
  ACTION=clear \
  RESUME_STATUS=in-progress
```

Behavior:

- clears all blocker governance fields
- moves the work item to `RESUME_STATUS`
- refuses `RESUME_STATUS=blocked`

## Backend Boundary

The supported command now calls the bounded broker workflow:

- `POST /v1/delivery-work-items/{work_item_id}/blocker`

So blocker management no longer depends on a direct Rails runner at the
operator surface.

## Dev-Integration Lane

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-manage-delivery-blocker \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  OPENPROJECT_DEPLOYMENT=devint-accepted-idea-delivery-openproject-web \
  TARGET_WORK_PACKAGE_ID=40 \
  ACTION=set \
  BLOCKER_STATEMENT="..." \
  BLOCKER_IMPACT="..." \
  BLOCKER_OWNER=mfshaf7 \
  BLOCKER_DISCOVERED_ON=2026-04-20 \
  BLOCKER_DECISION_PATH=workaround \
  BLOCKER_JUSTIFICATION="..." \
  BLOCKER_FOLLOW_UP_OWNER=mfshaf7 \
  BLOCKER_REVIEW_DATE=2026-04-24
```

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target work package
- confirm the work package status is `blocked` after `ACTION=set`
- confirm the blocker fields are populated
- after `ACTION=clear`, confirm the blocker fields are empty and the status has
  moved to `RESUME_STATUS`

## Related References

- [manage-proposal-to-delivery.md](manage-proposal-to-delivery.md)
- [start-delivery-execution.md](start-delivery-execution.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [manage-delivery-parking.md](manage-delivery-parking.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
