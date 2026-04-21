# 2026-04-21 Target PI View Alignment And Broker Create Wrapper

## Summary

`Workspace Delivery ART` now treats `Target PI` as the writable placement
signal for PI planning and PI objective views, and the product-scoped
`openproject-create-delivery-work-item` command now creates child work through
the broker-owned internal delivery API instead of a direct Rails runner path.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery execution
  - operator wrapper
  - PI planning views

## Ownership

- broker-owned delivery work-item create API and audit boundary:
  `operator-orchestration-service`
- OpenProject product wrapper, PI/view convergence, and operator runbooks:
  `platform-engineering`

## Root Cause

The first broker delivery slice left create on a direct platform-local Rails
path while PI planning views still depended on OpenProject version assignment.
The broker can write `Target PI` through the OpenProject API, but the version
link is not exposed as a writable field on the API form seam. Without
alignment, broker-created items would have been second-class citizens in the PI
views.

## Source Changes

- switched `openproject-create-delivery-work-item` to a thin broker wrapper
  that calls `POST /v1/delivery-work-items`
- kept PI/view convergence platform-owned by continuing to refresh the managed
  delivery views when `TARGET_PI` is supplied
- updated the PI planning and PI objective query model so managed views filter
  on the `Target PI` custom field instead of relying on direct version
  assignment on each work item
- updated the delivery ART contract and operator runbooks to reflect the new
  placement rule

## Live-State Impact

- no governed stage or prod change yet
- active `accepted-idea-delivery` dev-integration lane now proved the broker
  create path against the aligned `Target PI` planning model

## Artifact And Deployment Evidence

- deployment artifact:
  - dev-integration proof in `devint-accepted-idea-delivery-mfshaf7`
- proof artifact:
  - `.dev-integration/accepted-idea-delivery/mfshaf7/oos-task-62-create-proof.txt`

## Live Verification

- broker-backed create proof in the active devint lane:
  - `POST /v1/delivery-work-items`
  - created `work-item-70` / `openproject://work_packages/70`
  - parent `work-item-61`
  - `Target PI = PI-2026-02`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `git diff --check`

## Follow-Up

- prove broker-backed create in the active dev-integration lane
- migrate the next remaining workflow-shaped delivery commands behind the broker
