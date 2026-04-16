# Platform PostgreSQL Operations

## Primary Checks

```bash
k3s kubectl -n argocd get application platform-postgresql platform-postgresql-secrets
k3s kubectl -n platform-postgresql get all
```

## Related Procedures

- [../../../products/openproject/runbooks/bootstrap-openproject.md](../../../products/openproject/runbooks/bootstrap-openproject.md)
- [../../../products/openproject/runbooks/openproject-backup-restore.md](../../../products/openproject/runbooks/openproject-backup-restore.md)
