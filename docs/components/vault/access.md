# Vault Access

## Operator Path

- supported Windows/operator URL: `http://127.0.0.1:32200`

## WSL Fallback

```bash
k3s kubectl -n vault port-forward svc/vault-ui 8220:8200
```

Then open:

- `http://127.0.0.1:8220`

## Credentials

- operator access is provisioned by:
  [../../../scripts/bootstrap_operator_access.sh](../../../scripts/bootstrap_operator_access.sh)

Use the shared access matrix for the current credential model:

- [../../runbooks/access-platform-uis.md](../../runbooks/access-platform-uis.md)
