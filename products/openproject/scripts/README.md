# OpenProject Scripts

This directory contains OpenProject-specific platform-admin and repair
entrypoints for the platform integration.

These scripts are product-scoped. They are not shared platform tooling.

Delivery execution is broker-owned in
[`operator-orchestration-service`](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md).
This directory no longer carries the operator-facing ART read or mutation
surface.

The canonical machine-readable inventory for the remaining OpenProject product
runtime and platform-admin layer is:

- [../openproject-platform-admin-surface.json](../openproject-platform-admin-surface.json)

Workspace Proposals workflow-state storage is defined by:

- [../proposal-workflow-state.schema.json](../proposal-workflow-state.schema.json)

Validate the contract, script inventory, and required doc markers together
with:

```bash
python3 products/openproject/scripts/validate_openproject_platform_admin_surface.py --repo-root .
```

## Script Shape

The supported OpenProject script surface has two execution shapes:

- `*.sh`
  - supported platform-admin or repair entrypoints
  - these are the commands still exposed through `make` and the remaining
    OpenProject runbooks
- `*_runner.rb`
  - internal Rails runners used only by the remaining direct OpenProject
    admin/bootstrap entrypoints
  - these are implementation details, not the primary operator surface
- `*_support.rb`
  - shared helper modules used by multiple runners
- `*.py`
  - repo-local validators or broker-projection adapters invoked by shell entrypoints
  - includes the shared platform-admin adapter and the contract validator

If a script is not listed as a supported operator entrypoint below, treat it
as an implementation detail rather than a direct workflow surface.

For `Workspace Delivery ART`, the remaining entrypoints here cover:

- project bootstrap and schema provisioning
- ART view synchronization
- broker-projected ART quality and OpenProject projection-health reporting
- one-time ART normalization after a contract change
- clean-start and service-identity admin controls

The runner-backed platform-admin wrappers now share one adapter implementation:

- `openproject_platform_admin_adapter.py`

That adapter stages the contract-declared runner and support files by named
operation instead of duplicating raw pod copy-and-exec logic in each wrapper.
The shared `openproject_provision_identity.sh` helper now uses that same
adapter path so dependent callers can preserve the marked identity payload
contract without copying the provisioning runner directly. For local caller
bootstrap, the helper also supports `OPENPROJECT_API_TOKEN_OUTPUT_PATH` as the
explicit token-handoff destination instead of forcing direct runner access.

## Operator Entrypoints

- `openproject_apply.sh`
- `openproject_status.sh`
- `openproject_access.sh`
- `openproject_refresh_devint_access.sh`
- `openproject_sync_admin_password.sh`
- `openproject_configure_idea_backlog.sh`
- `openproject_configure_delivery_art.sh`
- `openproject_sync_delivery_art_views.sh`
- `openproject_check_delivery_art_quality.sh`
- `openproject_standardize_delivery_art.sh`
- `openproject_verify_clean_start.sh`
- `openproject_provision_delivery_art_identities.sh`
- `openproject_provision_operator_orchestration_identity.sh`
- `openproject_uninstall.sh`

## Supported OpenProject Make Targets

- `make openproject-apply`
- `make openproject-status`
- `make openproject-access`
- `make openproject-refresh-devint-access`
- `make openproject-sync-admin-password`
- `make openproject-configure-idea-backlog`
- `make openproject-configure-delivery-art`
- `make openproject-sync-delivery-art-views`
- `make openproject-check-delivery-art-quality`
- `make openproject-standardize-delivery-art`
- `make openproject-verify-clean-start`
- `make openproject-provision-delivery-art-identities`
- `make openproject-provision-operator-orchestration-identity`
- `make openproject-provision-operator-orchestration-delivery-access`
- `make openproject-uninstall`

## Retired Surface

The following command family is intentionally removed from this repo:

- ART portfolio and execution reads
- delivery initiative mutations
- delivery work-item mutations
- proposal-to-delivery consume and closeout execution
- normal-session ART workflow-health reads

Use the broker-owned delivery operator surface in
[`operator-orchestration-service`](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
instead of recreating local execution scripts.
