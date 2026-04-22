# 2026-04-22 OpenProject Broker Governance And Plan Apply Wrapper

## Summary

`openproject-update-delivery-initiative` and `openproject-apply-delivery-plan`
now act as thin OpenProject-side wrappers over the broker-owned delivery
initiative governance and plan/apply routes.

The platform still owns delivery view sync and the OpenProject runtime
boundary, but the operator surface no longer uses the direct Rails runner path
for these two workflow commands.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery governance
  - delivery plan application
  - operator wrapper

## Ownership

- broker governance and plan/apply routes:
  `operator-orchestration-service`
- OpenProject wrapper scripts, runbooks, and platform-owned view sync:
  `platform-engineering`

## Root Cause

The OpenProject operator surface still carried direct Rails-runner mutation
logic for initiative governance and plan application after the broker contract
for delivery workflow had already been established.

That left two workflow-shaped commands outside the intended broker seam and
blurred the boundary between workflow meaning and platform-admin concerns.

## Source Changes

- switched `products/openproject/scripts/openproject_update_delivery_initiative.sh`
  to exec into the broker pod and call
  `POST /v1/delivery-initiatives/{delivery_id}/governance`
- switched `products/openproject/scripts/openproject_apply_delivery_plan.sh`
  to exec into the broker pod and call
  `POST /v1/delivery-initiatives/{delivery_id}/plan/apply`
- kept delivery view sync on the platform side after governance and plan
  application when the PI view model needs refreshing
- updated the owning runbooks and delivery contract language to describe the
  broker-backed wrapper model explicitly

## Artifact And Deployment Evidence

- no live deployment artifact was produced in this workspace-only change
- the wrapper migration stays within the OpenProject product docs and scripts
  owned by `platform-engineering`

## Live Verification

- `bash -n products/openproject/scripts/openproject_update_delivery_initiative.sh`
- `bash -n products/openproject/scripts/openproject_apply_delivery_plan.sh`
- `bash -n products/openproject/scripts/openproject_sync_delivery_art_views.sh`
- `python3 scripts/validate_repo_structure.py --repo-root .`

## Follow-Up Actions

- keep the platform-owned view sync helper aligned with any future PI/version
  placement changes
- route any future delivery workflow meaning into the broker rather than back
  into direct Rails mutation at the OpenProject operator surface
