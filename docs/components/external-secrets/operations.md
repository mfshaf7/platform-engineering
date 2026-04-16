# External Secrets Operations

## Primary Checks

```bash
k3s kubectl -n argocd get application external-secrets
k3s kubectl -n external-secrets get deploy,pod
k3s kubectl get externalsecret -A
```

## Common Failure Signals

- `ExternalSecret` resources stop reconciling
- target Kubernetes secrets are stale or missing
- controller pods are healthy but secret values do not refresh
- failures correlate with Vault auth or network issues

## First Response

1. identify whether the failure is controller health, store configuration, or
   upstream Vault reachability
2. inspect one concrete failing `ExternalSecret` instead of starting from all
   namespaces at once
3. confirm whether the issue is platform-wide or isolated to a single product
   path

## Recovery Sequence

1. verify Argo and controller pod health
2. inspect the failing `ExternalSecret`
3. inspect the related `SecretStore` or `ClusterSecretStore`
4. if upstream secret access is failing, continue with Vault operations
5. after repair, verify the target Kubernetes secret was refreshed

## Evidence To Capture

Capture:

- failing `ExternalSecret`
- namespace and target secret
- store object in use
- controller pod state
- whether the root cause was Vault, network, auth, or bad object definition

## Related Components

When the issue is upstream secret availability or Vault connectivity, continue
with:

- [../vault/README.md](../vault/README.md)
- [../../runbooks/bootstrap-vault.md](../../runbooks/bootstrap-vault.md)
