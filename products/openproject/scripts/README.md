# OpenProject Scripts

This directory contains OpenProject-specific operator entrypoints for the
platform integration.

These scripts are product-scoped. They are not shared platform tooling.

For `Workspace Delivery ART`, these entrypoints now cover:

- PM² initiative governance on the top-level `Epic`
- SAFe-aligned delivery execution for `PI Objective`, `Feature`, `Enabler`,
  `User story`, `Task`, `Milestone`, and `Risk`
- PI views, PI-objective views, team/iteration planning summaries, explicit
  system-demo and inspect-and-adapt recording, ART-risk views, dependencies,
  blockers, parking, completion evidence, closeout readiness, and ART-quality
  validation

## Operator Entrypoints

- `openproject_apply.sh`
- `openproject_status.sh`
- `openproject_access.sh`
- `openproject_sync_admin_password.sh`
- `openproject_configure_idea_backlog.sh`
- `openproject_configure_delivery_art.sh`
- `openproject_sync_delivery_art_views.sh`
- `openproject_update_delivery_initiative.sh`
- `openproject_record_system_demo.sh`
- `openproject_record_inspect_and_adapt.sh`
- `openproject_create_delivery_work_item.sh`
- `openproject_bulk_update_delivery_work_items.sh`
- `openproject_move_delivery_work_item.sh`
- `openproject_update_delivery_work_item.sh`
- `openproject_complete_delivery_work_item.sh`
- `openproject_manage_delivery_dependency.sh`
- `openproject_show_delivery_initiatives.sh`
- `openproject_check_delivery_art_quality.sh`
- `openproject_show_delivery_execution.sh`
- `openproject_show_delivery_planning.sh`
- `openproject_show_pi_objectives.sh`
- `openproject_record_pi_review.sh`
- `openproject_check_delivery_closeout_readiness.sh`
- `openproject_manage_delivery_blocker.sh`
- `openproject_manage_delivery_parking.sh`
- `openproject_consume_accepted_idea.sh`
- `openproject_apply_delivery_plan.sh`
- `openproject_close_delivery_initiative.sh`
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
- `make openproject-sync-delivery-art-views`
- `make openproject-update-delivery-initiative`
- `make openproject-record-system-demo`
- `make openproject-record-inspect-and-adapt`
- `make openproject-create-delivery-work-item`
- `make openproject-bulk-update-delivery-work-items`
- `make openproject-move-delivery-work-item`
- `make openproject-update-delivery-work-item`
- `make openproject-complete-delivery-work-item`
- `make openproject-manage-delivery-dependency`
- `make openproject-show-delivery-initiatives`
- `make openproject-check-delivery-art-quality`
- `make openproject-show-delivery-execution`
- `make openproject-show-delivery-planning`
- `make openproject-show-pi-objectives`
- `make openproject-record-pi-review`
- `make openproject-check-delivery-closeout-readiness`
- `make openproject-manage-delivery-blocker`
- `make openproject-manage-delivery-parking`
- `make openproject-consume-accepted-idea`
- `make openproject-apply-delivery-plan`
- `make openproject-close-delivery-initiative`
- `make openproject-verify-clean-start`
- `make openproject-provision-operator-orchestration-identity`
- `make openproject-provision-operator-orchestration-delivery-access`
- `make openproject-uninstall`
