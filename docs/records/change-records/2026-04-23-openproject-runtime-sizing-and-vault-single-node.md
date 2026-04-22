---
security_evidence:
  review_areas:
    - runtime
    - secrets
  findings: []
  risks: []
  workstreams:
    - WS-007
---

# 2026-04-23 OpenProject runtime sizing and Vault single-node posture

## Summary

Reduced the platform OpenProject runtime contract to one Puma worker plus
GoodJob `maxThreads=10`, and reduced the shared workload Vault footprint from a
three-pod Raft set to a single-node Raft server. The Windows/bootstrap helper
inputs and the operator docs were updated in the same change so the PC install
path no longer assumes `vault-1` and `vault-2`.

## Classification

- owner repo: `platform-engineering`
- related control planes:
  - `operator-orchestration-service`
  - `security-architecture`
- trust-boundary areas:
  - runtime
  - secrets

## Ownership

- governed OpenProject and Vault environment contracts: `platform-engineering`
- devint OpenProject profile runtime shape: `operator-orchestration-service`
- secrets/recovery delta review authority: `security-architecture`

## Root Cause

The host memory profile showed the Rails app tier and the three-pod workload
Vault set consuming materially more memory than the current workstation runtime
needed. The Vault configuration also created a doctrine gap: source and helper
artifacts still implied an HA in-cluster quorum even though all replicas lived
on the same host and the active operator recovery path still centered on
`vault-0`.

## Source Changes

- bounded the OpenProject platform contract to:
  - `OPENPROJECT_WEB__WORKERS=1`
  - `workers.default.maxThreads=10`
- reduced `environments/shared/argocd/vault-app.yaml` to `ha.replicas: 1`
- changed the Windows/bootstrap source list for workload Vault pods to
  `vault-0` only
- re-rendered the generated Windows workload Vault unseal helper so the PC
  bootstrap path now targets `vault-0` only
- updated the Vault component and recovery docs so they describe the current
  single-node posture instead of an HA cluster

## Artifact And Deployment Evidence

- no new image build or artifact digest was required
- the governed live surfaces remain:
  - Argo application `openproject`
  - Argo application `vault`
  - generated Windows bootstrap helper
    `ansible/generated/platform-vault-unseal.ps1`

## Live Verification

- `make render-windows-bootstrap` completed after updating
  `platform_vault_pod_names`
- generated helper
  `ansible/generated/platform-vault-unseal.ps1` now renders:
  - `$VaultPods = @('vault-0')`
- generated OpenClaw scheduled-task bootstrap still invokes:
  - `platform-vault-unseal.ps1`
- `make -C /home/mfshaf7/projects/platform-engineering devint-up PROFILE=accepted-idea-delivery`
  completed after the runtime-sizing change
- live devint OpenProject verification:
  - `web_workers=1`
  - `good_job_max_threads=10`
- live Vault singleton convergence must come from the merged GitOps source,
  because `platform-root-shared` reconciles the child `vault` application from
  remote `main` and immediately reverts local child-app-only applies

## Follow-Up Actions

- if a real multi-node or cross-host Vault posture is required later, restore
  that as a deliberate governed design change instead of letting helper scripts
  drift there by default
- keep the devint OpenProject profile runtime aligned with the platform-managed
  OpenProject contract when future memory or throughput tuning changes land
