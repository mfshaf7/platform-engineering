# Move Delivery Work Item

## Purpose

Move one existing delivery work item under a different parent inside
`Workspace Delivery ART` through the supported broker-backed operator surface.

Use this when:

- the execution plan changed after the original decomposition
- an item belongs under a different `Feature`, `Enabler`, or `Epic`
- you need to correct hierarchy without recreating the work item
- a full plan reapply would be unnecessary or too broad

Use [update-delivery-work-item.md](update-delivery-work-item.md) for status,
assignee, PI, or description changes. Use
[create-delivery-work-item.md](create-delivery-work-item.md) when the child
does not exist yet.

## Command

Run from `platform-engineering/`:

```bash
make openproject-move-delivery-work-item \
  TARGET_WORK_PACKAGE_ID=40 \
  NEW_PARENT_WORK_PACKAGE_ID=43 \
  WORK_NOTE="Moved under the product-model feature after planning refined the split."
```

Required fields:

- `TARGET_WORK_PACKAGE_ID`
- `NEW_PARENT_WORK_PACKAGE_ID`

Optional fields:

- `WORK_NOTE`

Rules:

- the target and new parent must both live in `Workspace Delivery ART`
- the target and new parent must stay within the same delivery initiative
- the target cannot become its own parent
- the target cannot move under one of its descendants
- the move fails if the new parent type is not allowed for the target type
- the move fails if the new parent already has a sibling with the same
  `type + subject`
- the move keeps the existing status, PI, assignee, and description unless a
  separate update command changes them

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-move-delivery-work-item \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_WORK_PACKAGE_ID=40 \
  NEW_PARENT_WORK_PACKAGE_ID=43
```

## Expected Outcome

- the target work item is reparented under the new parent
- the move is executed through the broker route:
  - `POST /v1/delivery-work-items/{work_item_id}/move`
- the command prints the new parent linkage and previous parent linkage
- `WORK_NOTE` is recorded as a journal note when available, otherwise in the
  `Operator work notes` description section

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the new parent work item
- confirm the moved item now appears under the new parent
- open the moved item and confirm the work note, if supplied

## Related References

- [create-delivery-work-item.md](create-delivery-work-item.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
