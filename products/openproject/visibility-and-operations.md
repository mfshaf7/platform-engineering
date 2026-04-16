# Visibility And Operations

## Runtime Identity

- namespace: `openproject`
- Argo application: `openproject`
- secrets application: `openproject-secrets`

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
