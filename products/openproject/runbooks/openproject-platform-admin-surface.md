# OpenProject Platform-Admin Surface

## Purpose

Define the remaining OpenProject platform-admin controls after the normal ART
operator path moved to the broker.

Normal ART work should now use broker-owned reads and writes. The commands in
this runbook remain because they still manage OpenProject platform internals,
not because they are the supported day-to-day ART execution surface.

## Normal ART Operator Path

Use the broker-owned surface in `operator-orchestration-service` for:

- ART session bootstrap
- workflow health
- initiative review and closeout readiness
- planning repair
- work-item continuation and closeout
- guided initiative closeout

Primary operator entrypoint:

```bash
cd /home/mfshaf7/projects/operator-orchestration-service
npm run art -- bootstrap
npm run art -- workflow-health
```

## Platform-Admin Only

These commands remain platform-admin controls:

- `make openproject-configure-idea-backlog`
- `make openproject-configure-delivery-art`
- `make openproject-sync-delivery-art-views`
- `make openproject-standardize-delivery-art`
- `make openproject-provision-delivery-art-identities`
- `make openproject-provision-operator-orchestration-identity`
- `make openproject-sync-admin-password`
- `make openproject-verify-clean-start`

Use them only for:

- bootstrap and schema provisioning
- roadmap/board projection repair
- one-time normalization after contract changes
- identity and admin repair
- clean-start and runtime hygiene checks

## Remaining Rails Rule

The remaining direct OpenProject Rails runners are implementation details behind
these platform-admin commands only.

They are not the supported normal ART workflow for:

- session health
- scoped ART quality/readiness
- initiative review readiness
- work-item continuation
- ART reads or writes in normal delivery work

If a normal ART session needs any of those, go back to the broker route first.

## Related References

- [check-delivery-art-workflow-health.md](check-delivery-art-workflow-health.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
