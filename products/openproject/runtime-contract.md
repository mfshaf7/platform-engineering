# Runtime Contract

## Purpose

OpenProject provides an internal project-management service for local operator
use on the existing `k3s` cluster.

## Runtime Identity

- namespace: `openproject`
- Argo CD application: `openproject`
- secrets application: `openproject-secrets`
- Helm chart: `openproject/openproject`
- Vault auth role: `platform-openproject-prod-secrets`
- external database service: `platform-postgresql.platform-postgresql.svc.cluster.local:5432`

## Runtime Expectations

The platform-managed deployment must provide:

- a healthy Argo CD application in namespace `argocd`
- a reachable web UI on the cluster NodePort selected for Windows localhost use
- persistent application storage for `/var/openproject/assets`
- a reachable standalone PostgreSQL service for the application database
- a first-login admin password sourced from the platform secret path, not from Git
- governed release-state evidence for the current platform-owned contract under:
  - `environments/prod/openproject-release/stage-candidate.yaml`
  - `environments/prod/openproject-release/stage-verification.yaml`
  - `environments/prod/openproject-release/stage-readiness.yaml`
  - `environments/prod/openproject-release/prod-verification.yaml`

## Current Runtime Profile

- web deployment replica count: `1`
- Puma worker count: `1` via `OPENPROJECT_WEB__WORKERS`
- background worker deployment replica count: `1`
- GoodJob worker max threads: `10`
- no recorded scaling exemption currently exists for the OpenProject runtime

## Health And Readiness

V1 readiness is proven through:

- Argo CD sync status: `Synced`
- Argo CD health status: `Healthy`
- Kubernetes pod readiness in namespace `openproject`
- HTTP reachability of `/login`

Governed release readiness is stricter than runtime readiness. OpenProject is
not governed stage-ready or prod-verified from those signals alone; the
matching release-state objects still need current evidence for the exact
contract.

V1 does not add a dedicated Prometheus or version-metadata contract for
OpenProject yet.

If the proposal-to-delivery workflow is later activated in a real production
plane, that plane must also pass the production-activation hygiene gate from:

- `runbooks/prepare-production-clean-start.md`

## Access Model

- primary operator path: `http://127.0.0.1:32083`
- service exposure: fixed NodePort on the local `k3s` node
- Windows localhost reachability depends on the existing
  `PlatformCoreHostStack` bootstrap path refreshing local portproxy state
- WSL shell-local fallback should use `k3s kubectl -n openproject port-forward`
  rather than assuming the Windows localhost port is available in-shell

## Deferred In V1

- ingress, TLS, and domain-based access
- SSO or OIDC login
- external object storage
- dedicated observability integration
