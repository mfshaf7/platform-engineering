# Check Delivery ART Workflow Health

## Purpose

Use the broker-owned workflow-health read to decide whether the current
`Workspace Delivery ART` lane is healthy enough to trust before falling back to
deeper platform repair.

This is the first ART-lane health check now.

It exists to answer:

- is the roadmap projection still truthful to canonical `Target PI`?
- is the PM² board still truthful to stored initiative state?
- is the ART lane ready for normal broker-led operation, or is deeper repair
  needed?

## Primary Command

Run from `operator-orchestration-service/`:

```bash
npm run art -- workflow-health
```

This is the supported normal-session health surface. Do not replace it with a
direct Rails runner or an ad hoc OpenProject API dump.

## What It Returns

The broker workflow-health read surfaces:

- compatible OpenProject view truth for:
  - roadmap projection
  - PM² board projection
- roadmap projection drift
  - `Target PI` vs derived roadmap `version`
  - missing use of the derived backlog bucket
- PM² projection drift
  - active initiatives missing `PM² Phase`
  - done initiatives not kept in `Closing`
  - retired initiatives still retaining `PM² Phase`
- portfolio-level readiness counts for:
  - `Closing`
  - final closeout
  - retirement

## When To Use Deeper Checks

If workflow health is clean:

- continue with the normal broker-led ART path

If workflow health reports drift:

1. run the scoped ART quality gate for the affected initiative:

```bash
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=<namespace> \
  TARGET_EPIC_ID=<epic-id>
```

2. if the drift is roadmap or PM² view drift rather than execution drift, use
   the view-sync repair path:

```bash
make openproject-sync-delivery-art-views \
  OPENPROJECT_NAMESPACE=<namespace>
```

Do not jump straight to Rails-admin inspection for normal ART health. The
supported path is:

1. broker workflow health
2. scoped ART quality
3. platform-admin view repair only when the projection itself drifted

## Related References

- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [openproject-platform-admin-surface.md](openproject-platform-admin-surface.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
