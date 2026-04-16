# External Secrets Operations

## Primary Checks

```bash
k3s kubectl -n argocd get application external-secrets
k3s kubectl -n external-secrets get deploy,pod
k3s kubectl get externalsecret -A
```

## Related Components

When the issue is upstream secret availability or Vault connectivity, continue
with:

- [../vault/README.md](../vault/README.md)
- [../../runbooks/bootstrap-vault.md](../../runbooks/bootstrap-vault.md)
