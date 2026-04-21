# Record Inspect And Adapt

## Purpose

Append one timestamped inspect-and-adapt entry to the initiative-level
`Inspect & Adapt Actions` field on a delivery `Epic`.

Use this when a PI or iteration review produces improvement actions that should
stay attached to the initiative record as durable review history.

## Command

Run from `platform-engineering/`:

```bash
make openproject-record-inspect-and-adapt \
  TARGET_EPIC_ID=38 \
  INSPECT_DATE=2026-04-21 \
  INSPECT_SUMMARY="Iteration 1 review complete." \
  ACTION_ITEMS=$'- Add the first broker delivery-work-item update route\n- Keep proving operator surfaces in devint before shared rollout' \
  INSPECT_FOLLOW_UP="Review progress again during the next PI objective check."
```

Required fields:

- `TARGET_EPIC_ID`
- `INSPECT_SUMMARY`
- `ACTION_ITEMS`

Optional fields:

- `INSPECT_DATE`
- `INSPECT_FOLLOW_UP`

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-record-inspect-and-adapt \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38 \
  INSPECT_SUMMARY="Iteration 1 review complete." \
  ACTION_ITEMS=$'- Continue broker API migration'
```

## Expected Outcome

- the target `Epic` keeps its existing inspect-and-adapt history
- one new timestamped entry is appended
- the command prints the recorded entry details

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target initiative
- confirm the new entry appears under `Inspect & Adapt Actions`

## Related References

- [update-delivery-initiative.md](update-delivery-initiative.md)
- [record-system-demo.md](record-system-demo.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
