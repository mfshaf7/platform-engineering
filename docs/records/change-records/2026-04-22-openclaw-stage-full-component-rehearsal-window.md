# OpenClaw Stage Full-Component Rehearsal Window

## Date

- 2026-04-22

## Summary

The OpenClaw `stage` contract was expanded from the minimal rehearsal set
(`gateway,secrets,version`) to the full current stage component set
(`dashboards,gateway,observability,secrets,version`) so broader stage-based
security, observability, and operator validation can proceed in one deliberate
rehearsal window.

## Why

- the workspace is preparing to use `stage` for broader validation work instead
  of only narrow gateway rehearsal
- the stage bridge and gateway path were already healthy
- the next phase needs observability and dashboard surfaces available during
  stage testing

## Contract Change

- `environments/stage/argocd/kustomization.yaml`
  - added `observability-app.yaml`
  - added `platform-dashboards-app.yaml`

## Readiness Impact

- stage promotion readiness was reset to `pending`
- stage verification remained `pending`
- this is expected because any stage lifecycle change invalidates prior
  readiness and requires a fresh stage rehearsal before promotion

## Validation

- authoritative stage status showed the gateway bridge path ready before the
  expansion
- stage readiness state confirmed the current candidate and its required checks
  were still pending verification
- local stage contract readback showed the full component set after the change

## Follow-Up

- allow Argo CD to reconcile the updated stage root from `main`
- confirm the stage root now includes the added observability and dashboard
  applications
- record fresh stage verification evidence before any readiness approval or
  promotion decision
