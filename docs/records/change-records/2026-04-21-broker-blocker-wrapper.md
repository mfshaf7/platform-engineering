# 2026-04-21 Broker Blocker Wrapper

## Summary

`openproject-manage-delivery-blocker` is now a thin broker-backed operator
surface instead of a direct Rails-runner mutation path.

The OpenProject product surface still owns the operator command and runbook,
but the blocker workflow now goes through the broker-owned internal API:

- `POST /v1/delivery-work-items/{work_item_id}/blocker`

## Classification

- owner repo: `platform-engineering`
- related repo:
  - `operator-orchestration-service`
- product: `openproject`
- workflow area:
  - delivery execution
  - operator wrapper

## Ownership

- broker blocker route, request validation, audit, and backend adapter logic:
  `operator-orchestration-service`
- operator command, runbook, and product wrapper shape:
  `platform-engineering`

## Root Cause

After the broker already owned delivery summary, create, update, and move,
blocker management was still bypassing the broker through a direct OpenProject
Rails runner. That left another core delivery-control command outside the
intended workflow boundary.

## Source Changes

- switched `openproject_manage_delivery_blocker.sh` to a broker-backed wrapper
- updated the blocker runbook to document:
  - broker-backed execution
  - the bounded blocker route
  - preserved set and clear semantics

## Artifact And Deployment Evidence

- deployment artifact:
  - active devint broker rollout in `devint-accepted-idea-delivery-mfshaf7`
- proof artifact:
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-64-blocker-proof.txt`

## Live Verification

- broker route proof on `work-item-64`:
  - `set` wrote blocker state and moved the task to `blocked`
  - `clear` removed blocker state and returned the task to `in-progress`
- direct OpenProject readback confirmed the blocker fields persisted and then
  cleared
- `bash -n products/openproject/scripts/openproject_manage_delivery_blocker.sh`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- continue converting remaining workflow-shaped delivery commands into broker
  wrappers while keeping OpenProject admin controls platform-owned
