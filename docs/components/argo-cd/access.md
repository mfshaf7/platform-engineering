# Argo CD Access

## Operator Path

- supported Windows/operator URL: `https://127.0.0.1:32443`

## WSL Fallback

```bash
k3s kubectl -n argocd port-forward svc/argocd-server 8443:443
```

Then open:

- `https://127.0.0.1:8443`

## Credentials

- operator access is provisioned by:
  [../../../scripts/bootstrap_operator_access.sh](../../../scripts/bootstrap_operator_access.sh)

Use the shared access matrix for the current credential model:

- [../../runbooks/access-platform-uis.md](../../runbooks/access-platform-uis.md)
