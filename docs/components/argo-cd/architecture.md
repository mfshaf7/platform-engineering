# Argo CD Architecture

## Role

Argo CD is the shared GitOps control plane for this platform.

It owns:

- app-of-apps reconciliation
- sync and health state
- drift visibility
- the environment root application model

## Current Live Shape

- namespace: `argocd`
- root applications:
  - `platform-root-shared`
  - `platform-root-prod`
  - `platform-root-stage`
- current server service: `argocd-server`

## Model

Argo CD is the cluster control-plane boundary between approved Git state and
the live workloads running in `k3s`.

The current model is:

- `platform-root-shared`
  - shared control-plane services
- `platform-root-prod`
  - prod product workloads and prod-only shared services
- `platform-root-stage`
  - stage workloads only when stage is deliberately resumed

## Read With

- [../../architecture/overview.md](../../architecture/overview.md)
- [../../architecture/control-planes.md](../../architecture/control-planes.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
