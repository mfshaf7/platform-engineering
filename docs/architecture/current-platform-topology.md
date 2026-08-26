# Current Platform Topology

## Purpose

This document describes the platform that is actually deployed today.

It is an observed live-state surface, not the target steady-state architecture.

Use it when you need to answer practical operator questions such as:

- what components exist right now
- which Argo applications own them
- which namespaces they live in
- which surfaces are directly reachable
- which things are intentionally internal-only or suspended

Last validated against the live local cluster on `2026-04-19`.

That date applies to the governed Argo topology. The isolated WGCF
dev-integration profile described below was validated separately on
`2026-08-09`.

## Read This With

- [../components/README.md](../components/README.md)
- [overview.md](overview.md)
- [../runbooks/access-platform-uis.md](../runbooks/access-platform-uis.md)
- [../../products/openclaw/runbooks/access-openclaw.md](../../products/openclaw/runbooks/access-openclaw.md)
- [../../products/openproject/runbooks/access-openproject.md](../../products/openproject/runbooks/access-openproject.md)

## Current Argo Layout

The platform uses an app-of-apps model rooted in three Argo applications:

| Root application | Git path | Role | Current live outcome |
| --- | --- | --- | --- |
| `platform-root-shared` | `environments/shared/argocd` | Shared control-plane services and shared secret-delivery assets | Deploys shared services such as Vault, External Secrets, and operator-orchestration-service |
| `platform-root-prod` | `environments/prod/argocd` | Production product workloads and production-only shared services | Deploys OpenProject, PostgreSQL, prod observability, and prod dashboards; OpenClaw prod is currently suspended through the governed lifecycle contract |
| `platform-root-stage` | `environments/stage/argocd` | Stage-only workloads and shared product support surfaces | Currently resumed for the OpenClaw stage gateway plus stage secrets and stage version while stage observability remains absent |

## Current Live Argo Applications

As of `2026-04-19`, the cluster reports these live Argo applications:

- `external-secrets`
- `openclaw-gateway-stage`
- `openproject`
- `openproject-secrets`
- `operator-orchestration-service`
- `platform-observability-prod`
- `platform-dashboards-prod`
- `platform-postgresql`
- `platform-postgresql-secrets`
- `platform-root-prod`
- `platform-root-shared`
- `platform-root-stage`
- `platform-secrets-stage`
- `platform-version-stage`
- `vault`

That means the platform is not "just OpenClaw". The current live shared and
product-integrated stack includes:

- Argo CD
- Vault
- External Secrets Operator
- operator-orchestration-service
- prod observability
- OpenClaw stage
- OpenProject
- shared PostgreSQL

OpenClaw prod is intentionally absent from the current live app set because its
governed prod lifecycle is presently `suspended`.

## Namespace Inventory

| Namespace | Current role | Current state |
| --- | --- | --- |
| `argocd` | GitOps control plane and Argo applications | Active and populated |
| `vault` | Vault cluster and UI/API service | Active and populated |
| `external-secrets` | External Secrets Operator | Active and populated |
| `observability` | prod Prometheus, Alertmanager, Grafana, operator auth proxy, dashboards | Active and populated |
| `observability-stage` | stage observability namespace | Exists but currently empty because stage observability remains suspended |
| `openclaw` | prod OpenClaw namespace | Active but currently empty because prod OpenClaw is suspended |
| `openclaw-stage` | stage OpenClaw namespace | Active and populated for the current gateway rehearsal window |
| `openproject` | OpenProject web application | Active and populated |
| `operator-orchestration-service` | shared workflow broker | Active and populated |
| `platform-postgresql` | shared PostgreSQL service for platform products | Active and populated |

## Operator-Scoped Dev-Integration Runtime

Dev-integration profiles are local iteration lanes, not Argo-managed stage or
production topology. The retained WGCF proof used this bounded namespace
outside the Argo application inventory; the evidence-storage lifecycle remains
dormant until the workspace registry activation reaches remote `main`:

| Namespace | Owner | Populated workloads | Exposure | Current state |
| --- | --- | --- | --- | --- |
| `devint-governance-control-fabric-mfshaf7` | WGCF dev-integration profile | WGCF API and migration, PostgreSQL, MinIO object storage, exact maintenance Job | ClusterIP only; operator access through the shared profile runner or explicit loopback port-forward | Historical local proof retained; current evidence-storage actions dormant pending registry activation; no stage or production authority |

The storage Service, StatefulSet, 2Gi PVC, application credential, root
credential, and NetworkPolicy are profile-owned. OOS and OpenProject receive no
object-store URL or credential. See
[ADR-019](../decisions/adr/ADR-019-wgcf-dev-integration-evidence-storage.md)
and the [WGCF operations guide](../components/workspace-governance-control-fabric/operations.md).

## Operator-Facing Surfaces

These are the current direct operator-facing surfaces:

| Surface | Namespace | Owning app | Exposure model | Current state |
| --- | --- | --- | --- | --- |
| Argo CD | `argocd` | shared control plane | NodePort plus Windows localhost proxy | Live |
| Vault UI and API | `vault` | `vault` | NodePort plus Windows localhost proxy | Live |
| Grafana (prod) | `observability` | `platform-observability-prod` plus `platform-dashboards-prod` | NodePort plus Windows localhost proxy | Live |
| Prometheus (prod) | `observability` | `platform-observability-prod` via `platform-operator-ui-auth-proxy` | NodePort plus Windows localhost proxy | Live |
| Alertmanager (prod) | `observability` | `platform-observability-prod` via `platform-operator-ui-auth-proxy` | NodePort plus Windows localhost proxy | Live |
| OpenProject | `openproject` | `openproject` | NodePort plus Windows localhost proxy | Live |
| OpenClaw prod gateway | `openclaw` | `openclaw-gateway` | ClusterIP only; primary user surface is Telegram | Currently suspended through the governed prod lifecycle |
| OpenClaw stage gateway | `openclaw-stage` | `openclaw-gateway-stage` | ClusterIP only; primary user surface is Telegram | Live for the current stage stabilization window |

For exact URLs, credentials, and shell-local fallback commands, use
[../runbooks/access-platform-uis.md](../runbooks/access-platform-uis.md).

For per-component architecture and operations, use:

- [../components/argo-cd/README.md](../components/argo-cd/README.md)
- [../components/vault/README.md](../components/vault/README.md)
- [../components/observability/README.md](../components/observability/README.md)
- [../components/external-secrets/README.md](../components/external-secrets/README.md)
- [../components/operator-orchestration-service/README.md](../components/operator-orchestration-service/README.md)
- [../components/platform-postgresql/README.md](../components/platform-postgresql/README.md)
- [../components/governed-ai-gateway/README.md](../components/governed-ai-gateway/README.md)

## Internal-Only Or Currently Absent Surfaces

These surfaces should not be documented as if they are directly reachable today:

- `platform-postgresql`
  - internal-only cluster service
  - no direct operator UI
- External Secrets Operator
  - controller only
  - no platform UI
- `operator-orchestration-service`
  - internal-only shared broker service
  - no direct operator UI
- WGCF dev-integration evidence storage
  - internal-only, operator-scoped local service
  - no public, Windows localhost, stage, or production access path
- OpenClaw prod gateway
  - no dedicated browser UI today
  - currently absent because prod OpenClaw is suspended
- stage Grafana, stage Prometheus, stage Alertmanager
  - configured in source for stage use
  - not currently deployed because stage observability remains suspended
- `governed-ai-gateway`
  - local `dev-integration` profile source exists for access-plane proof
  - no Argo-managed stage or prod deployment exists
  - no model profile is activated by this topology entry
- Temporal controlled commissioning
  - source profile is active, but the runtime is absent from the current live
    cluster pending Workspace binding #1019 and merged-runtime proof #1020
  - the registered composition may create one collision-resistant operator-scoped local
    Kubernetes namespace and Temporal namespace with separate OOS API, OOS
    worker, and WGCF worker identities
  - no direct profile launch, direct Console access, shared UI, or persistent
    live namespace is authorized by this source-only activation

## Access Model Clarification

The supported human-operator path is Windows localhost, refreshed by
`PlatformCoreHostStack`.

From WSL:

- do not assume `127.0.0.1:<port>` reaches the Windows portproxy path
- use `k3s kubectl port-forward ...` when you need a shell-local endpoint
- treat product access runbooks as the owner for product-specific entrypoints

## Update Rule

Whenever any of these change, update this document in the same change:

- a new Argo application is added or removed
- a namespace changes role
- a NodePort or Windows localhost access path changes
- a product becomes directly reachable or stops being directly reachable
- stage or prod exposure posture changes
- a product gains a governed suspend or quarantine posture
