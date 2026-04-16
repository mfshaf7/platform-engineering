# Platform PostgreSQL Operations

## Primary Checks

```bash
k3s kubectl -n argocd get application platform-postgresql platform-postgresql-secrets
k3s kubectl -n platform-postgresql get all
```

## Common Failure Signals

- application pods depending on PostgreSQL fail readiness or database
  connections
- PostgreSQL pod is running but not accepting connections
- credentials or injected secrets changed and downstream apps did not recover
- backup or restore work is needed for the only current consumer, OpenProject

## First Response

1. confirm whether the failure is PostgreSQL availability, credentials, or the
   consuming product
2. verify platform-postgresql and platform-postgresql-secrets Argo app state
3. check whether OpenProject is the only impacted consumer or whether a
   broader platform problem exists

## Recovery Sequence

1. verify Argo app health and pod state
2. confirm database service reachability
3. confirm secret delivery if credentials recently changed
4. use the product backup and restore runbook only when data recovery is the
   actual problem

## Evidence To Capture

Capture:

- PostgreSQL pod and service state
- affected consuming product
- whether the issue was availability, credentials, or data integrity
- restore evidence if backup or restore was performed

## Related Procedures

- [../../../products/openproject/runbooks/bootstrap-openproject.md](../../../products/openproject/runbooks/bootstrap-openproject.md)
- [../../../products/openproject/runbooks/openproject-backup-restore.md](../../../products/openproject/runbooks/openproject-backup-restore.md)
