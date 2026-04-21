# Check Delivery Closeout Readiness

## Purpose

Check whether a delivery `Epic` is truly ready for closeout before moving the
source proposal from `accepted` to `implemented`.

Use this when you need an explicit gate that proves:

- the delivery `Epic` itself is `done`
- there are no open descendants left under that `Epic`
- there are no active blocker records left under that `Epic`
- every `done` descendant carries explicit completion evidence

This is the operator-facing closeout gate. The closeout helper also enforces it
before calling the broker-owned internal closeout path.

## Command

Run from `platform-engineering/`:

```bash
make openproject-check-delivery-closeout-readiness \
  TARGET_EPIC_ID=38
```

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-check-delivery-closeout-readiness \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38
```

## Expected Outcome

The command prints JSON with:

- the target `Epic`
- `ready_for_closeout`
- machine-readable `reasons`
- summary counts for descendants, statuses, blockers, PI, and assignees
- `open_descendants`
- `parked_items`
- `blocked_items`
- `completed_without_evidence`

Exit behavior:

- exits `0` when the delivery initiative is ready for closeout
- exits non-zero when the initiative is not ready
- parked descendants are reported but do not block closeout by themselves

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target `Epic`
- confirm the epic is `done`
- confirm no descendant work items remain outside `done` or `parked`
- confirm no blocker fields remain active
- confirm each `done` descendant carries:
  - `Completion Summary`
  - `Changed Surfaces`
  - `Test Result Evidence`
  - `Validation Evidence`

## Related References

- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [close-delivery-initiative.md](close-delivery-initiative.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [manage-delivery-blocker.md](manage-delivery-blocker.md)
- [manage-delivery-parking.md](manage-delivery-parking.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
