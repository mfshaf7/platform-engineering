# Platform Naming Audit

## Purpose

Track remaining places where platform-owned components still carry `openclaw`
product naming.

## Renamed In This Change

- shared Argo roots now use `platform-root-*`
- shared Argo project now uses `platform-core`
- shared Vault and ESO secret plumbing now uses `platform-*` names
- product secret data in Vault now lives under `products/openclaw/...`

## Remaining Product-Coupled Names To Review

- [charts/openclaw-gateway](../../charts/openclaw-gateway)
- [environments/stage/argocd/openclaw-gateway-app.yaml](../../environments/stage/argocd/openclaw-gateway-app.yaml)
- [environments/prod/argocd/openclaw-gateway-app.yaml](../../environments/prod/argocd/openclaw-gateway-app.yaml)

These are intentionally still product-owned today because they describe the
OpenClaw workload, not the shared platform substrate.

## Current Audit Result

- no remaining shared Argo root or AppProject names use the `openclaw` prefix
- no remaining shared Vault or ESO control-plane names use the `openclaw`
  prefix
- the remaining `openclaw-*` names in this repo are primarily product runtime,
  namespace, image, repo, and host-integration names

## Rule Going Forward

- platform substrate names must be product-neutral
- product workloads keep product-specific names
- shared secret paths should be product-scoped beneath a neutral platform root
