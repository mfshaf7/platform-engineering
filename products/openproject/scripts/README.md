# OpenProject Scripts

This directory contains OpenProject-specific operator entrypoints for the
platform integration.

These scripts are product-scoped. They are not shared platform tooling.

## Operator Entrypoints

- `openproject_apply.sh`
- `openproject_status.sh`
- `openproject_access.sh`
- `openproject_sync_admin_password.sh`
- `openproject_configure_idea_backlog.sh`
- `openproject_configure_delivery_art.sh`
- `openproject_consume_accepted_idea.sh`
- `openproject_verify_clean_start.sh`
- `openproject_provision_operator_orchestration_identity.sh`
- `openproject_uninstall.sh`

## Supported OpenProject Make Targets

- `make openproject-apply`
- `make openproject-status`
- `make openproject-access`
- `make openproject-sync-admin-password`
- `make openproject-configure-idea-backlog`
- `make openproject-configure-delivery-art`
- `make openproject-consume-accepted-idea`
- `make openproject-verify-clean-start`
- `make openproject-provision-operator-orchestration-identity`
- `make openproject-provision-operator-orchestration-delivery-access`
- `make openproject-uninstall`
