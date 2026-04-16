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

Use the access runbook for the current direct access model and shell-local
fallback:

- [runbooks/access-openproject.md](runbooks/access-openproject.md)

## Version And Package Evidence

Operators should be able to identify:

- upstream chart version
- upstream application version
- dependency versions recorded in this product directory

## Functional Checks

Minimum meaningful checks:

- operator login page reachable
- admin password sync completed
- PostgreSQL dependency reachable
- application pod stable after reconciliation

Backup and restore procedure lives in:

- [runbooks/openproject-backup-restore.md](runbooks/openproject-backup-restore.md)
