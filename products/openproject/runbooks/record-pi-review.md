# Record PI Review

## Purpose

Record PI-objective review outcomes for one initiative and one PI through a
supported operator workflow.

Use this when a PI review has finished and you need to capture:

- objective-level `Actual Business Value`
- objective-level `PI Objective Review Outcome`
- optional per-objective review notes

This is separate from [record-inspect-and-adapt.md](record-inspect-and-adapt.md).
PI review records the objective outcomes. Inspect and Adapt records the
follow-up improvement actions at the initiative layer.

## Review File Shape

Use a JSON file with this schema:

```json
{
  "schema_version": 1,
  "reviews": [
    {
      "target_work_package_id": 58,
      "actual_business_value": 8,
      "review_outcome": "Met",
      "review_note": "The committed API-boundary slice was completed within PI-2026-02."
    },
    {
      "target_work_package_id": 59,
      "actual_business_value": 5,
      "review_outcome": "Partially met",
      "review_note": "Execution reporting landed, but bulk API migration is still pending."
    }
  ]
}
```

Supported keys:

- `target_work_package_id`
- `actual_business_value`
- `review_outcome`
- `review_note`

## Command

Run from `platform-engineering/`:

```bash
make openproject-record-pi-review \
  TARGET_EPIC_ID=38 \
  TARGET_PI=PI-2026-02 \
  PI_REVIEW_FILE=/abs/path/pi-review.json
```

Optional fields:

- `PI_REVIEW_DATE`

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-record-pi-review \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38 \
  TARGET_PI=PI-2026-02 \
  PI_REVIEW_FILE=/abs/path/pi-review.json
```

## Expected Outcome

- the targeted descendant `PI Objective` records are updated
- `Actual Business Value` and `PI Objective Review Outcome` are both visible on
  each reviewed objective
- optional review notes are appended to the objective description under
  `PI Review Notes`
- the command prints a JSON summary with outcome counts and total actual
  business value

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target initiative
- review the `PI Objectives` board or the objective records directly
- confirm `Actual Business Value` and `PI Objective Review Outcome` match the
  review file
- confirm any review notes appear under `PI Review Notes`

For the aggregate view, compare with:

- [show-pi-objectives.md](show-pi-objectives.md)
- [show-delivery-initiatives.md](show-delivery-initiatives.md)

## Related References

- [show-pi-objectives.md](show-pi-objectives.md)
- [record-inspect-and-adapt.md](record-inspect-and-adapt.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
