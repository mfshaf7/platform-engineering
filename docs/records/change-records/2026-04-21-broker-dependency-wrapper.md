# 2026-04-21 Broker Dependency Wrapper

## Summary

`openproject-manage-delivery-dependency` is now a thin broker-backed operator
surface instead of a direct Rails-runner mutation path.

The OpenProject product surface still owns the operator command and runbook,
but the dependency workflow now goes through the broker-owned internal API:

- `POST /v1/delivery-work-items/{work_item_id}/dependency`

## Classification

- owner repo: `platform-engineering`
- related repo:
  - `operator-orchestration-service`
- product: `openproject`
- workflow area:
  - delivery execution
  - operator wrapper

## Ownership

- broker dependency route, request validation, audit, and backend adapter
  logic: `operator-orchestration-service`
- operator command, runbook, and product wrapper shape:
  `platform-engineering`

## Root Cause

After the broker already owned delivery summary, create, update, move, and
blocker management, dependency management was still bypassing the broker
through a direct OpenProject Rails runner. That left another core
delivery-control command outside the intended workflow boundary.

## Source Changes

- switched `openproject_manage_delivery_dependency.sh` to a broker-backed
  wrapper
- updated the dependency runbook to document:
  - broker-backed execution
  - the bounded dependency route
  - preserved predecessor/target semantics

## Artifact And Deployment Evidence

- deployment artifact:
  - active devint broker rollout in `devint-accepted-idea-delivery-mfshaf7`
- proof artifact:
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-65-dependency-proof.txt`

## Live Verification

- broker route proof on one disposable dependency pair:
  - `set` created the expected predecessor-scoped relation
  - `clear` removed it cleanly
- broker execution summary reflected the unresolved dependency during the proof
- `bash -n products/openproject/scripts/openproject_manage_delivery_dependency.sh`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- continue converting remaining workflow-shaped delivery commands into broker
  wrappers while keeping OpenProject admin controls platform-owned
