# 2026-04-22 OpenClaw Stage Full-Component Rehearsal Window

## Summary

The OpenClaw `stage` contract was expanded from the minimal rehearsal set
(`gateway,secrets,version`) to the full current stage component set
(`dashboards,gateway,observability,secrets,version`) so broader stage-based
security, observability, and operator validation can proceed in one deliberate
rehearsal window.

## Classification

- owner repo: `platform-engineering`
- product: `openclaw`
- workflow area:
  - stage lifecycle
  - observability and dashboard support
  - governed rehearsal readiness

## Ownership

- OpenClaw stage lifecycle and stage root contract: `platform-engineering`
- shared supporting components already present in the platform:
  - `vault`
  - `external-secrets`
  - `operator-orchestration-service`
  - `openproject`

## Root Cause

The authoritative stage bridge and gateway path were healthy, but the governed
stage contract was still limited to the minimal promotion-ready runtime set.

That was sufficient for narrow gateway rehearsal but not for the broader stage
usage now needed, where product validation must happen alongside the supporting
observability and dashboard surfaces. The gap was therefore not a broken stage
gateway; it was an under-scoped stage contract relative to the next rehearsal
goal.

## Source Changes

- updated `environments/stage/argocd/kustomization.yaml` to add:
  - `observability-app.yaml`
  - `platform-dashboards-app.yaml`
- stage lifecycle control automatically reset:
  - `environments/stage/verification.yaml`
  - `environments/stage/promotion-readiness.yaml`
  so the new stage footprint cannot be mistaken for an already-verified or
  already-approved candidate

## Artifact And Deployment Evidence

- deployment artifact:
  - Git-managed stage root contract under
    `environments/stage/argocd/kustomization.yaml`
- no new gateway image or digest was created
- the existing stage candidate remains:
  - source bundle `f51f50083f7c`
  - digest `sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`

## Live Verification

- authoritative stage status before expansion:
  - `active:gateway,secrets,version`
  - `stage_bridge:ready service=openclaw-host-bridge-stage.service`
- governed readiness status before expansion:
  - `status=pending`
  - `required_components=gateway,secrets,version`
  - `verification_status=pending`
- stage lifecycle controller expanded the requested component set to:
  - `dashboards,gateway,observability,secrets,version`
- local stage contract readback after the change shows:
  - `openclaw-gateway-app.yaml`
  - `platform-secrets-app.yaml`
  - `platform-version-app.yaml`
  - `observability-app.yaml`
  - `platform-dashboards-app.yaml`
- shared/supporting live components already present and healthy:
  - `openclaw-observability`
  - `vault`
  - `external-secrets`
  - `operator-orchestration-service`
  - `openproject`

## Follow-Up

- land the updated stage contract to `main` so Argo CD can reconcile the full
  stage component set from the governed source of truth
- confirm `platform-root-stage` now surfaces the added stage applications
- run fresh stage rehearsal checks and record
  `environments/stage/verification.yaml`
- keep readiness `pending` until that fresh stage evidence exists
