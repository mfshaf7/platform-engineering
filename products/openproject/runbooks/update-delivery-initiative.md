# Update Delivery Initiative

## Purpose

Update the top-level `Epic` in `Workspace Delivery ART` through the supported
operator surface instead of ad hoc Rails commands or manual field hunting in
the UI. The platform command is now a thin wrapper over the broker-owned
initiative governance route.

Use this when you need to change:

- `PM² Phase`
- `Target PI`
- `Sponsor`
- `Business Objective`
- `Success Criteria`
- `System Demo Evidence`
- `Inspect & Adapt Actions`
- initiative-level `NFR Category`
- top-level delivery status
- top-level delivery description

Use the dedicated runbooks below when you want to append timestamped review
history instead of replacing the entire field body:

- [record-system-demo.md](record-system-demo.md)
- [record-inspect-and-adapt.md](record-inspect-and-adapt.md)

## Command

Run from `platform-engineering/`:

```bash
make openproject-update-delivery-initiative \
  TARGET_EPIC_ID=38 \
  PM2_PHASE=Planning \
  TARGET_PI=PI-2026-02 \
  SPONSOR=mfshaf7 \
  SYSTEM_DEMO_EVIDENCE="PI-2026-02 system demo planned for the full broker execution path." \
  INSPECT_AND_ADAPT_ACTIONS="- Capture follow-up improvements after the first PI review." \
  STATUS=in-progress
```

Optional fields:

- `BUSINESS_OBJECTIVE`
- `SUCCESS_CRITERIA`
- `SYSTEM_DEMO_EVIDENCE`
- `INSPECT_AND_ADAPT_ACTIONS`
- `NFR_CATEGORY`
- `DESCRIPTION`

For the `accepted-idea-delivery` dev-integration lane, also set the namespace:

```bash
make openproject-update-delivery-initiative \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38 \
  PM2_PHASE=Planning \
  TARGET_PI=PI-2026-02 \
  SPONSOR=mfshaf7 \
  STATUS=in-progress
```

## Expected Outcome

- the target delivery `Epic` reflects the requested governance fields
- the target `Epic` status changes when `STATUS` is supplied
- the target `Epic` is assigned to the supplied PI version when `TARGET_PI` is supplied
- managed delivery-art views are refreshed when `TARGET_PI` is supplied

## Backend Boundary

The command now calls:

- `POST /v1/delivery-initiatives/{delivery_id}/governance`

The OpenProject runbook stays platform-owned, but the workflow meaning lives
behind the broker route.
When `TARGET_PI` is supplied, the wrapper still refreshes the managed delivery
views through the platform-owned sync helper.

## Verification

In the OpenProject UI:

- open `Workspace Delivery ART`
- open the target `Epic`
- confirm `PM² Phase`, `Target PI`, `Sponsor`, `Business Objective`, and
  `Success Criteria` match the intended values
- confirm `System Demo Evidence`, `Inspect & Adapt Actions`, and initiative-level
  `NFR Category` match the intended values when supplied

If `TARGET_PI` was supplied:

- run [show-delivery-initiatives.md](show-delivery-initiatives.md) or
  [show-delivery-planning.md](show-delivery-planning.md)
- confirm the target `Epic` and its descendants roll up under the expected PI

## Related References

- [manage-proposal-to-delivery.md](manage-proposal-to-delivery.md)
- [start-delivery-execution.md](start-delivery-execution.md)
- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [record-system-demo.md](record-system-demo.md)
- [record-inspect-and-adapt.md](record-inspect-and-adapt.md)
