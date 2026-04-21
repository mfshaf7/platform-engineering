# Show PI Objectives

## Purpose

Show the PI-objective review surface for one delivery `Epic` through a
supported read-only operator workflow.

Use this when you need to inspect:

- committed versus stretch objective counts
- reviewed versus not-yet-reviewed objective counts
- objective status by PI
- planned versus actual business-value rollups
- PI objective review outcomes
- which objectives still lack acceptance criteria or ready-contract data
- how objectives are distributed by team and iteration

## Command

Run from `platform-engineering/`:

```bash
make openproject-show-pi-objectives \
  TARGET_EPIC_ID=38
```

Optional fields:

- `TARGET_PI`

Example:

```bash
make openproject-show-pi-objectives \
  TARGET_EPIC_ID=38 \
  TARGET_PI=PI-2026-02
```

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-show-pi-objectives \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38 \
  TARGET_PI=PI-2026-02
```

## Expected Outcome

The command prints JSON with:

- the top-level `Epic`
- objective counts, including committed and stretch totals
- review counts and review-outcome distribution
- planned, actual, and delta business-value totals
- gap counts for missing acceptance criteria or ready-contract data
- rollups by status, PI, team, and iteration
- one entry per descendant `PI Objective`

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target initiative
- review the `PI Objectives` board or objective work packages directly
- confirm the PI objective type, review outcome, business values, and status
  match the summary

## Related References

- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [show-delivery-planning.md](show-delivery-planning.md)
- [record-pi-review.md](record-pi-review.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
