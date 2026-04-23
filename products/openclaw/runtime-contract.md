# Runtime Contract

## Purpose

OpenClaw provides the platform's AI runtime and typed host-control integration.

This document describes how OpenClaw is expected to exist on this platform, not
how the upstream or component source repos are implemented.

It is the intended steady-state and governed lifecycle contract for OpenClaw on
this platform, not a snapshot of what is live today.

For the platform-side architecture and repo boundary model, see
[architecture-and-owner-model.md](architecture-and-owner-model.md).

## Runtime Identity

- prod namespace: `openclaw`
- prod Argo CD application: `openclaw-gateway`
- supporting prod applications:
  - `platform-secrets-prod`
  - `platform-version`
- prod lifecycle contract:
  - `environments/prod/openclaw-lifecycle.yaml`
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
- a governed prod lifecycle profile using the shared runtime-lifecycle
  vocabulary:
  - `live`
  - `traffic-stopped`
  - `suspended`
  - `quarantined`
- stage suspended by default unless a deliberate rehearsal is in progress
- release-state evidence under:
  - `environments/stage/release-candidate.yaml`
  - `environments/stage/verification.yaml`
  - `environments/stage/promotion-readiness.yaml`
    - OpenClaw's retained product-local filename for the standardized stage
      readiness decision because that same record is the promotion gate
  - `environments/prod/verification.yaml` for post-promotion prod smoke or UAT

OpenClaw may also use a separate Telegram overlay artifact lane for small
Telegram-only fixes on a platform-qualified base line:

- separate immutable Telegram overlay artifact
- init-container copy into `/app/extensions/telegram`
- explicit contract state in `environments/stage/versions.yaml` and
  `environments/prod/versions.yaml`
- stage qualification of the exact overlay digest before any prod use
- prod promotion only when the overlay is bound to the same qualified base
  image as the approved stage candidate

## Current Runtime Profile

- stage gateway replica count: `1` when stage is resumed
- prod gateway replica count: `1`
- no recorded scaling exemption currently exists for the gateway runtime

## Health And Readiness

Minimum platform-level readiness for OpenClaw is:

- Argo sync status: `Synced`
- Argo health status: `Healthy`
- pod readiness in namespace `openclaw`
- gateway `/healthz`
- gateway `/readyz`
- at least one real functional verification through Telegram or product flow

Health alone is not enough for OpenClaw promotion.

Promotion approval is still stage-gated, but a user-facing prod rollout is not
operationally complete until post-promotion prod smoke is recorded against the
current prod contract.

Prod lifecycle is separate from promotion. Promotion may update the prod
contract while prod is `traffic-stopped` or `suspended`, but the governed prod
lifecycle still decides whether the OpenClaw prod gateway is present and
whether user traffic is allowed. `traffic-stopped` is enforced at the
deployment boundary by removing the prod gateway application while leaving
selected support surfaces available. When prod is `quarantined`, promotion is
blocked until the lifecycle leaves quarantine.

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
