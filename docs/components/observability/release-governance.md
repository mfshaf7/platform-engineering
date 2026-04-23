# Observability Release Governance

## Purpose

The shared observability stack and the platform-owned dashboard assets are
`supporting components`. They do not use a standalone product promotion lane,
but stage and prod still require explicit verification and support-readiness
truth for the exact contracts that expose Grafana, Prometheus, Alertmanager,
and the platform dashboard assets.

## Current Governance Shape

### Observability Stack Contracts

- stage contract:
  - [../../../environments/stage/argocd/observability-app.yaml](../../../environments/stage/argocd/observability-app.yaml)
- prod contract:
  - [../../../environments/prod/argocd/observability-app.yaml](../../../environments/prod/argocd/observability-app.yaml)

Current release records:

- [../../../environments/stage/observability-release/stage-verification.yaml](../../../environments/stage/observability-release/stage-verification.yaml)
- [../../../environments/stage/observability-release/stage-support-readiness.yaml](../../../environments/stage/observability-release/stage-support-readiness.yaml)
- [../../../environments/prod/observability-release/prod-verification.yaml](../../../environments/prod/observability-release/prod-verification.yaml)
- [../../../environments/prod/observability-release/prod-support-readiness.yaml](../../../environments/prod/observability-release/prod-support-readiness.yaml)

### Platform Dashboard Asset Contracts

- stage contract:
  - [../../../environments/stage/argocd/platform-dashboards-app.yaml](../../../environments/stage/argocd/platform-dashboards-app.yaml)
- prod contract:
  - [../../../environments/prod/argocd/platform-dashboards-app.yaml](../../../environments/prod/argocd/platform-dashboards-app.yaml)

Current release records:

- [../../../environments/stage/platform-dashboards-release/stage-verification.yaml](../../../environments/stage/platform-dashboards-release/stage-verification.yaml)
- [../../../environments/stage/platform-dashboards-release/stage-support-readiness.yaml](../../../environments/stage/platform-dashboards-release/stage-support-readiness.yaml)
- [../../../environments/prod/platform-dashboards-release/prod-verification.yaml](../../../environments/prod/platform-dashboards-release/prod-verification.yaml)
- [../../../environments/prod/platform-dashboards-release/prod-support-readiness.yaml](../../../environments/prod/platform-dashboards-release/prod-support-readiness.yaml)

Stage observability is currently suspended. The stage verification and
support-readiness records should stay `inactive` until the stage contracts are
deliberately resumed.

## Operator Flow

### 1. Update Or Confirm The Environment Contract

When the stack or asset overlay changes, update the exact environment contract
first:

- `observability-app.yaml` for the stack itself
- `platform-dashboards-app.yaml` for the Grafana asset overlay

### 2. Reset The Dependent Records When The Contract Changes

Refresh the affected verification and support-readiness files under:

- [../../../environments/stage/observability-release/](../../../environments/stage/observability-release/)
- [../../../environments/prod/observability-release/](../../../environments/prod/observability-release/)
- [../../../environments/stage/platform-dashboards-release/](../../../environments/stage/platform-dashboards-release/)
- [../../../environments/prod/platform-dashboards-release/](../../../environments/prod/platform-dashboards-release/)

### 3. Rehearse The Active Contract

Use the current operator surfaces to prove, for the exact contract under test:

- Argo still matches the expected stack or asset contract
- the supported Grafana, Prometheus, and Alertmanager paths behave as expected
- the auth proxy, datasource, and dashboard assets still match the intended
  environment
- dashboard overlays still register correctly against the Grafana host for the
  environment

### 4. Record Verification

Write the exact rehearsal result into the lane-specific verification file with:

- the exact environment contract reference
- an operator-reviewable `evidenceRef`
- explicit per-check results for the active stack or asset pack

### 5. Record Support Readiness

Update the matching stage or prod support-readiness file only after the exact
verification record exists for the same contract.

## Evidence Rule

One healthy pod set, one working UI, or one rendered dashboard alone does not
make the observability surface ready. The record must tie the exact contract
to reviewable proof and the exact verification result for the environment.

## Related Components

- [grafana.md](grafana.md)
- [prometheus.md](prometheus.md)
- [alertmanager.md](alertmanager.md)
- [operations.md](operations.md)
- [../../standards/governed-release-control-model.md](../../standards/governed-release-control-model.md)
