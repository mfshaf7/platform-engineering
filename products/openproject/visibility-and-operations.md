# Visibility And Operations

## Runtime Identity

- namespace: `openproject`
- Argo application: `openproject`
- secrets application: `openproject-secrets`
- direct product UI: `http://127.0.0.1:32083` on the supported Windows
  operator path

## Health And Readiness

V1 operational checks are:

- Argo sync status `Synced`
- Argo health status `Healthy`
- pod readiness in namespace `openproject`
- HTTP reachability of `/login`

## Logs And Diagnostics

Primary evidence surfaces:

- Argo application state
- Kubernetes pod logs
- namespace workload status
- localhost operator access path
- governed release-state records under
  `environments/prod/openproject-release/`

Use the access runbook for the current direct access model and shell-local
fallback:

- [runbooks/access-openproject.md](runbooks/access-openproject.md)

The same runbook records the separate local-only access path for the
`accepted-idea-delivery` dev-integration instance. Its NodePort and Windows
localhost mapping are access plumbing only; profile status remains the source
for that instance's runtime and credential state.

## Version And Package Evidence

Operators should be able to identify:

- upstream chart version
- upstream application version
- dependency versions recorded in this product directory
- current governed stage candidate and prod verification state

## Functional Checks

Minimum meaningful checks:

- operator login page reachable
- admin password sync completed
- PostgreSQL dependency reachable
- application pod stable after reconciliation

The current governed release catalogs publish those checks in machine-readable
form:

- [verification-catalog.yaml](verification-catalog.yaml)
- [prod-verification-catalog.yaml](prod-verification-catalog.yaml)

Before activating a real production proposal-to-delivery workflow, also run:

- [runbooks/prepare-production-clean-start.md](runbooks/prepare-production-clean-start.md)

Backup and restore procedure lives in:

- [runbooks/openproject-backup-restore.md](runbooks/openproject-backup-restore.md)
