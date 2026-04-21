# Record System Demo

## Purpose

Append one timestamped system-demo entry to the initiative-level
`System Demo Evidence` field on a delivery `Epic`.

Use this when a PI or iteration demo has happened and you want the initiative
record to carry a durable, additive review history instead of overwriting the
entire field body through generic editing.

## Command

Run from `platform-engineering/`:

```bash
make openproject-record-system-demo \
  TARGET_EPIC_ID=38 \
  DEMO_DATE=2026-04-21 \
  DEMO_OUTCOME=reviewed \
  DEMO_SUMMARY="Iteration 1 demo covered the SAFe-aligned delivery operator surface." \
  DEMO_EVIDENCE="Reviewed planning, PI objective, risk, and execution summaries in the devint ART." \
  DEMO_FOLLOW_UP="Continue broker API migration under Feature #51."
```

Required fields:

- `TARGET_EPIC_ID`
- `DEMO_SUMMARY`
- `DEMO_EVIDENCE`

Optional fields:

- `DEMO_DATE`
- `DEMO_OUTCOME`
- `DEMO_FOLLOW_UP`

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-record-system-demo \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38 \
  DEMO_SUMMARY="Iteration 1 demo complete" \
  DEMO_EVIDENCE="Reviewed PI objective progress and risk posture."
```

## Expected Outcome

- the target `Epic` keeps its existing `System Demo Evidence`
- one new timestamped entry is appended
- the command prints the recorded entry details

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target initiative
- confirm the new system-demo entry appears under `System Demo Evidence`

## Related References

- [update-delivery-initiative.md](update-delivery-initiative.md)
- [record-inspect-and-adapt.md](record-inspect-and-adapt.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
