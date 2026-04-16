# Current Platform Topology

## Purpose

This document describes the platform that is actually deployed today.

Use it when you need to answer practical operator questions such as:

- what components exist right now
- which Argo applications own them
- which namespaces they live in
- which surfaces are directly reachable
- which things are intentionally internal-only or suspended

Last validated against the live local cluster on `2026-04-16`.

## Read This With

- [overview.md](overview.md)
- [../runbooks/access-platform-uis.md](../runbooks/access-platform-uis.md)
- [../../products/openclaw/runbooks/access-openclaw.md](../../products/openclaw/runbooks/access-openclaw.md)
- [../../products/openproject/runbooks/access-openproject.md](../../products/openproject/runbooks/access-openproject.md)

## Current Argo Layout

The platform uses an app-of-apps model rooted in three Argo applications:

| Root application | Git path | Role | Current live outcome |
| --- | --- | --- | --- |
| `platform-root-shared` | `environments/shared/argocd` | Shared control-plane services and shared secret-delivery assets | Deploys shared services such as Vault and External Secrets |
| `platform-root-prod` | `environments/prod/argocd` | Production product workloads and production-only shared services | Deploys OpenClaw prod, OpenProject, PostgreSQL, prod observability, dashboards, and prod secrets/version assets |
| `platform-root-stage` | `environments/stage/argocd` | Stage-only workloads | Currently suspended; only a suspend sentinel is applied and no stage child apps are live |

## Current Live Argo Applications

As of `2026-04-16`, the cluster reports these live Argo applications:

- `external-secrets`
- `openclaw-gateway`
- `openclaw-observability`
- `openproject`
- `openproject-secrets`
- `platform-dashboards-prod`
- `platform-postgresql`
- `platform-postgresql-secrets`
- `platform-root-prod`
- `platform-root-shared`
- `platform-root-stage`
- `platform-secrets-prod`
- `platform-version`
- `vault`

That means the platform is not "just OpenClaw". The current live shared and
product-integrated stack includes:

- Argo CD
- Vault
- External Secrets Operator
- prod observability
- OpenClaw prod
- OpenProject
- shared PostgreSQL

## Namespace Inventory

| Namespace | Current role | Current state |
| --- | --- | --- |
| `argocd` | GitOps control plane and Argo applications | Active and populated |
| `vault` | Vault cluster and UI/API service | Active and populated |
| `external-secrets` | External Secrets Operator | Active and populated |
| `observability` | prod Prometheus, Alertmanager, Grafana, operator auth proxy, dashboards | Active and populated |
| `observability-stage` | stage observability namespace | Exists but currently empty because stage is suspended |
| `openclaw` | prod OpenClaw gateway | Active and populated |
| `openclaw-stage` | stage OpenClaw namespace | Exists but currently empty because stage is suspended |
| `openproject` | OpenProject web application | Active and populated |
| `platform-postgresql` | shared PostgreSQL service for platform products | Active and populated |

## Operator-Facing Surfaces

These are the current direct operator-facing surfaces:

| Surface | Namespace | Owning app | Exposure model | Current state |
| --- | --- | --- | --- | --- |
| Argo CD | `argocd` | shared control plane | NodePort plus Windows localhost proxy | Live |
| Vault UI and API | `vault` | `vault` | NodePort plus Windows localhost proxy | Live |
| Grafana (prod) | `observability` | `openclaw-observability` plus `platform-dashboards-prod` | NodePort plus Windows localhost proxy | Live |
| Prometheus (prod) | `observability` | `openclaw-observability` via `platform-operator-ui-auth-proxy` | NodePort plus Windows localhost proxy | Live |
| Alertmanager (prod) | `observability` | `openclaw-observability` via `platform-operator-ui-auth-proxy` | NodePort plus Windows localhost proxy | Live |
| OpenProject | `openproject` | `openproject` | NodePort plus Windows localhost proxy | Live |
| OpenClaw prod gateway | `openclaw` | `openclaw-gateway` | ClusterIP only; primary user surface is Telegram | Live, but not a browser UI |

For exact URLs, credentials, and shell-local fallback commands, use
[../runbooks/access-platform-uis.md](../runbooks/access-platform-uis.md).

## Internal-Only Or Currently Absent Surfaces

These surfaces should not be documented as if they are directly reachable today:

- `platform-postgresql`
  - internal-only cluster service
  - no direct operator UI
- External Secrets Operator
  - controller only
  - no platform UI
- OpenClaw gateway
  - no dedicated browser UI today
  - use Telegram for user interaction and port-forward only for operator checks
- stage Grafana, stage Prometheus, stage Alertmanager
  - configured in source for stage use
  - not currently deployed while stage remains suspended
- stage OpenClaw gateway
  - configured in source for rehearsals
  - not currently deployed while stage remains suspended

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
