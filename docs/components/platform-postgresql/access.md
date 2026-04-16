# Platform PostgreSQL Access

This service is internal-only by default.

For operator shell access, use port-forward:

```bash
k3s kubectl -n platform-postgresql port-forward svc/platform-postgresql 5432:5432
```

Do not document database passwords in Git-tracked docs.
