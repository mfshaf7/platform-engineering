# Runtime Contract

## Purpose

OpenClaw provides the platform's AI runtime and typed host-control integration.

This document describes how OpenClaw is expected to exist on this platform, not
how the upstream or component source repos are implemented.

For the platform-side architecture and repo boundary model, see
[architecture-and-owner-model.md](architecture-and-owner-model.md).

## Runtime Identity

- prod namespace: `openclaw`
- prod Argo CD application: `openclaw-gateway`
- supporting prod applications:
  - `platform-secrets-prod`
  - `platform-version`
- prod service: `openclaw-gateway.openclaw.svc.cluster.local:18789`
- prod exposure model: ClusterIP only; no dedicated browser UI
- stage namespace: `openclaw-stage` when resumed
- current active build/composition owner: `openclaw-runtime-distribution`

## Runtime Expectations

The platform-managed deployment must provide:

- a healthy Argo CD application in namespace `argocd`
- a reachable gateway service inside the cluster
- health and readiness endpoints
- version and build evidence
- Vault-backed runtime secret delivery
- configured bridge and host-recovery dependencies
- stage suspended by default unless a deliberate rehearsal is in progress

## Health And Readiness

Minimum platform-level readiness for OpenClaw is:

- Argo sync status: `Synced`
- Argo health status: `Healthy`
- pod readiness in namespace `openclaw`
- gateway `/healthz`
- gateway `/readyz`
- at least one real functional verification through Telegram or product flow

Health alone is not enough for OpenClaw promotion.

## Access Model

- primary user-facing surface: Telegram
- no shared browser dashboard for OpenClaw itself
- operator shell access uses `k3s kubectl port-forward` when direct inspection
  is needed
- shared operator dashboards such as Argo, Grafana, Prometheus, and Vault are
  documented in shared platform docs, not here

See:

- [runbooks/access-openclaw.md](runbooks/access-openclaw.md)
- [../../docs/runbooks/access-platform-uis.md](../../docs/runbooks/access-platform-uis.md)

## Deferred

- dedicated product web UI
- ingress and domain-based access
- product-specific SSO
