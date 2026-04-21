# Close Delivery Initiative

## Purpose

This is the primary operator workflow for closing a completed delivery `Epic`
in `Workspace Delivery ART` and moving the source proposal in
`Workspace Proposals` from `accepted` to `implemented`.

Use it when:

- the consumed delivery `Epic` is truly complete
- the delivery item already has status `done`
- the source proposal should stop acting like active intake and become terminal
  traceability only

## Current Truth

- `Workspace Proposals` remains the proposal-of-record until closeout
- `Workspace Delivery ART` remains the execution-of-record during delivery
- source proposal closeout is broker-owned and internal-only
- the source proposal must not be marked `implemented` until the linked
  delivery record is actually `done`

The current supported operator path is:

- run the closeout-readiness gate
- run the product-scoped closeout helper
- verify the source proposal moved to `implemented` and retained its delivery
  backlink

## Before You Start

Confirm these are already true:

- OpenProject is reachable:
  - `make openproject-access`
- the source proposal already has a linked `Delivery Ref`
- the linked delivery `Epic` is already `done`
- the linked delivery `Epic` passes:
  - `make openproject-check-delivery-closeout-readiness TARGET_EPIC_ID=<epic-id>`
- the delivery closeout note is ready and attributable
- every `done` descendant already carries explicit completion evidence

## Command

Run from `platform-engineering/`:

```bash
make openproject-close-delivery-initiative \
  IDEA_ID=idea-37 \
  CLOSEOUT_NOTES="Delivered through the first bounded productization execution slice." \
  OPERATOR_ID=mfshaf7 \
  OPERATOR_HANDLE=mfshaf7
```

For the persistent `accepted-idea-delivery` dev-integration lane, also set the
broker namespace override:

```bash
make openproject-close-delivery-initiative \
  BROKER_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  IDEA_ID=idea-37 \
  CLOSEOUT_NOTES="Delivered through the first bounded productization execution slice." \
  OPERATOR_ID=mfshaf7 \
  OPERATOR_HANDLE=mfshaf7
```

## Expected Outcome

- the broker verifies the linked delivery record is `done`
- the helper refuses closeout when the linked delivery epic still has open descendants or active blockers
- the source proposal moves from `accepted` to `implemented`
- the source proposal keeps its `Delivery Ref`
- the delivery record keeps its `Origin Idea Ref`
- the broker read projection exposes the closeout result and closeout notes

## Verification

In `Workspace Proposals`, confirm:

- the source proposal status is now `implemented`
- `Delivery Ref` still points at the delivery record

In `Workspace Delivery ART`, confirm:

- the delivery `Epic` still has status `done`
- `Origin Idea Ref` still points back to the source idea id

Minimum broker verification:

- `GET /v1/ideas/{idea_id}` now reports `status = implemented`
- `delivery_ref` still points at the same delivery record
- `delivery_closeout_notes` matches the supplied closeout note

## Related References

- [manage-proposal-to-delivery.md](manage-proposal-to-delivery.md)
- [start-delivery-execution.md](start-delivery-execution.md)
- [check-delivery-closeout-readiness.md](check-delivery-closeout-readiness.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
