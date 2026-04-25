# 2026-04-25 OpenProject Broker Quality Path And Admin Boundary

## Summary

The normal `Workspace Delivery ART` quality and workflow-health path now stays
inside the broker-owned operator surface. The platform-owned OpenProject
integration keeps only the remaining platform-admin controls that still depend
on OpenProject internals such as board or roadmap projection repair, bootstrap,
and one-time normalization.

## Classification

- owner repo: `platform-engineering`
- product: `openproject`
- workflow area:
  - delivery execution
  - ART quality
  - OpenProject platform-admin controls

## Ownership

- normal ART read and mutation surface:
  `operator-orchestration-service`
- OpenProject product runtime, view projection repair, and platform-admin
  controls:
  `platform-engineering`

## Root Cause

The broker already owned the normal ART operator surface, but the platform
quality checker still depended on a direct Rails dump inside the OpenProject
pod. Product docs also still read as though OpenProject-admin and Rails-backed
paths were the default ART session surface. That left the architecture split
correct in principle but blurry in daily operation.

## Source Changes

- switched the platform ART quality wrapper to the broker-native
  `/v1/delivery-session/quality-pack` read
- added a dedicated workflow-health runbook for the broker-owned first ART
  health check
- added a dedicated OpenProject platform-admin runbook that defines the
  remaining Rails-backed admin-only surfaces
- updated the OpenProject product contract, runbook index, and script index so
  the broker path is the normal ART surface and OpenProject-admin remains only
  the repair/bootstrap layer
- updated the platform quality-check tests to match the new broker-native path

## Artifact And Deployment Evidence

- the platform quality wrapper no longer needs to push a direct Rails dump
  runner into the OpenProject pod for normal ART quality execution
- the remaining Rails-backed controls are explicitly documented as
  platform-admin only

## Live Verification

- `python3 products/openproject/scripts/test_openproject_check_delivery_art_quality.py`
- `python3 scripts/validate_repo_structure.py --repo-root .`
- `python3 scripts/validate_governance_docs.py --repo-root .`
- `python3 scripts/validate_operational_docs.py --repo-root .`
- `make openproject-check-delivery-art-quality OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 TARGET_EPIC_ID=304 INCLUDE_DONE=true`

## Follow-Up

- continue moving remaining normal ART health and readiness reads into the
  broker-owned session surfaces
- keep the OpenProject product scripts focused on platform-admin lifecycle and
  projection repair instead of recreating normal ART operator reads
