# Change Record

## Summary

- Date: 2026-04-17
- Short title: First governed OpenClaw prod suspend test required finalizer fix
- Environment: prod
- Severity: high

## Classification

- Type: platform lifecycle control defect plus live containment
- User-facing impact: the first governed prod suspend removed the OpenClaw prod
  Argo Application objects from the prod root, but the live runtime resources
  stayed up until the orphaned OpenClaw slice was cleaned up manually.

## Ownership

- Owning repo or layer: `platform-engineering`
- Related repos: `security-architecture`
- Related ADR: `docs/decisions/adr/ADR-010-governed-openclaw-prod-lifecycle.md`

## Root Cause

- Immediate failure: the prod lifecycle contract switched to `suspended`, but
  the deleted OpenClaw prod child Applications did not prune their live
  resources.
- Actual root cause: the prod child Application manifests
  `openclaw-gateway-app.yaml`, `platform-secrets-app.yaml`, and
  `platform-version-app.yaml` were missing
  `resources-finalizer.argocd.argoproj.io`.
- Why it escaped earlier controls: the initial prod lifecycle implementation
  validated the root kustomization and lifecycle config, but it did not verify
  that the managed prod child Applications carried the Argo resource finalizer
  required for clean prune on deletion.

## Source Changes

- Repo: `platform-engineering`
- Commit(s):
  - `3fd8134d46a8f6558d56e36ff98bbf1253ea2fc9`
  - `ac61e4a44e365e444926678ad8c1586271980665`
- Guardrail added:
  - prod managed OpenClaw Application manifests now include
    `resources-finalizer.argocd.argoproj.io`
  - `products/openclaw/scripts/prod_lifecycle.py` now fails validation if the
    required finalizers are missing
  - `products/openclaw/runbooks/manage-prod-lifecycle.md` and ADR-010 now
    document that prod suspend must prune live runtime resources, not only drop
    child app objects

## Artifact And Deployment Evidence

- Build workflow run: none; this change exercised the prod lifecycle control,
  not a new gateway build
- Published image tag: existing prod contract remained
  `gateway-1fb1b11b4142`
- Published digest:
  `sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`
- Recorded prod revision:
  - suspend merge: `5ac1f64e2f32e12ecd42d3d0553879137f3894e9`
  - finalizer guardrail merge: `7734e829d434501c8ef1bc385afcc0413ba4b287`
- Argo application revision: `platform-root-prod` reconciled to
  `7734e829d434501c8ef1bc385afcc0413ba4b287`

## Host Or Runtime Recovery

- Required host/runtime action: manually delete the orphaned OpenClaw prod
  runtime resources after the first suspend because the child Applications had
  already been removed without prune.
- Why it was environment drift instead of source defect: once the prod contract
  was already `suspended`, the remaining live deployment, service, ExternalSecret,
  SecretStore, service account, generated secret, and version ConfigMap were
  orphaned runtime objects that no longer matched the governed Git state.
- Recovery command or procedure:
  - `k3s kubectl -n openclaw delete deployment/openclaw-gateway`
  - `k3s kubectl -n openclaw delete service/openclaw-gateway configmap/platform-versions`
  - `k3s kubectl -n openclaw delete externalsecrets.external-secrets.io/openclaw-gateway-secrets`
  - `k3s kubectl -n openclaw delete secret/openclaw-gateway-secrets`
  - `k3s kubectl -n openclaw delete secretstores.external-secrets.io/platform-vault serviceaccount/platform-vault-reader`

## Live Verification

- App health: `platform-root-prod` is `Synced Healthy` on revision
  `7734e829d434501c8ef1bc385afcc0413ba4b287`
- Deployed image: no live OpenClaw prod gateway remained after containment;
  the suspended prod contract still points to
  `ghcr.io/mfshaf7/openclaw-gateway@sha256:348acf9bbbbe1714b6f41b13e2d1dec367d98f85b3bd7c00ef8b17f1b6eb790e`
- Pod: no prod OpenClaw gateway pod remained in namespace `openclaw`
- Functional verification:
  - `openclaw-prod-lifecycle` ConfigMap reports
    `state=suspended changedBy=mfshaf7 reason=stage-stabilization-window`
  - Argo no longer shows `openclaw-gateway`, `platform-secrets-prod`, or
    `platform-version` Applications in `argocd`
  - namespace `openclaw` is reduced to only `serviceaccount/default` and
    `configmap/kube-root-ca.crt`
- Residual risk: the durable finalizer fix is merged, but the clean
  live-with-finalizers `live -> suspended` prune cycle has not yet been
  re-exercised because prod is intentionally staying quiet after containment.

## Follow-Up

- Required follow-up: the next deliberate `prod live -> prod suspended` drill
  should verify that the merged finalizers now prune the OpenClaw prod slice
  without manual cleanup.
- Optional hardening: teach the prod lifecycle validation or runbook to call
  out the exact orphaned-runtime cleanup targets when a suspend request lands on
  a cluster that still carries pre-finalizer child Applications.
- Owner: platform engineering
