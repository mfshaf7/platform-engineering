# 2026-04-21 Broker Move Wrapper

## Summary

`openproject-move-delivery-work-item` is now a thin broker-backed operator
surface instead of a direct Rails-runner mutation path.

The OpenProject product surface still owns the operator command and runbook,
but the hierarchy mutation now goes through the broker-owned internal API:

- `POST /v1/delivery-work-items/{work_item_id}/move`

## Classification

- owner repo: `platform-engineering`
- related repo:
  - `operator-orchestration-service`
- product: `openproject`
- workflow area:
  - delivery execution
  - operator wrapper

## Ownership

- broker move route, request validation, audit, and backend adapter logic:
  `operator-orchestration-service`
- operator command, runbook, and product wrapper shape:
  `platform-engineering`

## Root Cause

After the broker already owned delivery read, create, and update, work-item
move was still bypassing the broker through a direct OpenProject Rails runner.
That left one core delivery-control command outside the intended workflow
boundary.

## Source Changes

- switched `openproject_move_delivery_work_item.sh` to a broker-backed wrapper
- updated the runbook to reflect:
  - broker-backed execution
  - same-initiative constraint
  - unsupported parent-type rejection

## Live-State Impact

- no governed stage or prod change
- active devint delivery work now proves the move route through the broker

## Artifact And Deployment Evidence

- deployment artifact:
  - active devint broker rollout in `devint-accepted-idea-delivery-mfshaf7`
- proof artifact:
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-63-move-proof.txt`

## Live Verification

- broker route proof moved `work-item-70`:
  - `61 -> 39`
  - `39 -> 61`
- direct OpenProject readback confirmed the final parent returned to `61`
- broker execution-summary readback confirmed `node70.parent_id = 61`
- `bash -n products/openproject/scripts/openproject_move_delivery_work_item.sh`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- continue migrating the remaining workflow-shaped delivery commands behind the
  broker while keeping platform-owned wrappers thin
