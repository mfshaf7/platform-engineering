# Manage Delivery Dependency

## Purpose

Record or remove one explicit execution dependency between two delivery work
items inside `Workspace Delivery ART` through the supported operator surface.

This command is broker-backed. The OpenProject product surface keeps the
operator command and runbook, but the dependency workflow executes through the
internal broker route:

- `POST /v1/delivery-work-items/{work_item_id}/dependency`

Use this when:

- one delivery item cannot start or complete until another item finishes
- you need explicit predecessor visibility outside informal notes or chat
- you want the dependency to appear in the execution summary surfaces

Operator semantics:

- `TARGET_WORK_PACKAGE_ID` depends on `DEPENDS_ON_WORK_PACKAGE_ID`

The underlying OpenProject relation is stored as `follows`, but operators
should reason about it as a dependency, not as raw relation internals.

## Command

Run from `platform-engineering/`:

```bash
make openproject-manage-delivery-dependency \
  ACTION=set \
  TARGET_WORK_PACKAGE_ID=41 \
  DEPENDS_ON_WORK_PACKAGE_ID=40
```

Optional fields for `ACTION=set`:

- `LAG=<integer>`
- `CLEAR_LAG=true`
- `DESCRIPTION="..."`
- `CLEAR_DESCRIPTION=true`

Rules:

- `LAG` and `CLEAR_LAG=true` are mutually exclusive
- `DESCRIPTION` and `CLEAR_DESCRIPTION=true` are mutually exclusive
- a work item cannot depend on itself
- both work items must belong to `Workspace Delivery ART`
- duplicate links between the same predecessor and target are collapsed to one record

Remove a dependency:

```bash
make openproject-manage-delivery-dependency \
  ACTION=clear \
  TARGET_WORK_PACKAGE_ID=41 \
  DEPENDS_ON_WORK_PACKAGE_ID=40
```

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-manage-delivery-dependency \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  ACTION=set \
  TARGET_WORK_PACKAGE_ID=41 \
  DEPENDS_ON_WORK_PACKAGE_ID=40
```

## Expected Outcome

- the dependency is created, updated, or removed without direct UI-only editing
- the command prints the effective relation, including lag and description when present
- `openproject-show-delivery-execution` reflects the dependency in:
  - per-item dependency fields
  - `dependency_relations`
  - unresolved dependency counts when the predecessor is not `done`

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target work item
- inspect the relations area and confirm the predecessor link is present or removed

In the supported CLI surfaces:

```bash
make openproject-show-delivery-execution TARGET_EPIC_ID=38
```

Confirm the target item shows the expected dependency and unresolved state.

## Backend Boundary

Ownership split:

- broker route, request validation, audit, and OpenProject relation adapter:
  `operator-orchestration-service`
- operator command and OpenProject runbook surface:
  `platform-engineering`

## Related References

- [show-delivery-execution.md](show-delivery-execution.md)
- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [update-delivery-work-item.md](update-delivery-work-item.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
