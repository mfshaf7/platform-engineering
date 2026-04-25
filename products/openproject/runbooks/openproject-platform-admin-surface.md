# OpenProject Platform-Admin Surface

## Purpose

Define the remaining OpenProject platform-admin controls after the normal ART
operator path moved to the broker.

Normal ART work should now use broker-owned reads and writes. The commands in
this runbook remain because they still manage OpenProject platform internals,
not because they are the supported day-to-day ART execution surface.

## Canonical Contract

The machine-readable source of truth for this boundary is:

- [../openproject-platform-admin-surface.json](../openproject-platform-admin-surface.json)

That contract enumerates:

- supported OpenProject runtime and platform-admin shell entrypoints
- the remaining Rails-backed internal runners behind those entrypoints
- internal helper scripts and support modules
- the residual runner that still exists only as a retirement candidate
- the docs that must keep pointing at the same boundary model

Validate the contract and inventory together with:

```bash
python3 products/openproject/scripts/validate_openproject_platform_admin_surface.py --repo-root .
```

The runner-backed platform-admin wrappers now stage those internals through the
shared adapter:

- `products/openproject/scripts/openproject_platform_admin_adapter.py`

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

## Product Runtime Compatibility Surface

These commands still belong to the OpenProject product runtime and do not move
into the broker:

- `make openproject-apply`
- `make openproject-status`
- `make openproject-access`
- `make openproject-uninstall`

They are product runtime controls, not ART delivery execution controls.

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

The canonical command inventory lives in
[../openproject-platform-admin-surface.json](../openproject-platform-admin-surface.json)
instead of only in this prose runbook.

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

The currently active Rails-backed internals remain:

- `openproject_configure_idea_backlog_runner.rb`
- `openproject_configure_delivery_art_runner.rb`
- `openproject_sync_delivery_art_views_runner.rb`
- `openproject_standardize_delivery_art_runner.rb`
- `openproject_provision_identity_runner.rb`

The supported runner-backed platform wrappers no longer implement their own raw
pod copy-and-exec flow. They now call the shared adapter, which stages the
declared runner and support files by named operation before invoking
`bundle exec rails runner`.

That now includes the shared identity-provisioning helper used by the supported
identity wrapper scripts, so dependent callers can keep their existing marked
JSON payload and token handoff behavior without bypassing the admin surface.
When a dependent caller needs the issued token locally instead of Vault storage,
the helper now supports `OPENPROJECT_API_TOKEN_OUTPUT_PATH` as the explicit
local handoff path while still keeping stdout sanitized.

## Related References

- [check-delivery-art-workflow-health.md](check-delivery-art-workflow-health.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [sync-delivery-art-views.md](sync-delivery-art-views.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
