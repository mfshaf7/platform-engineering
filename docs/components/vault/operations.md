# Vault Operations

## Primary Checks

```bash
k3s kubectl -n vault get pods
k3s kubectl -n vault exec vault-0 -- vault status
```

## Shared Procedures

- [../../runbooks/bootstrap-vault.md](../../runbooks/bootstrap-vault.md)
- [../../runbooks/vault-recovery.md](../../runbooks/vault-recovery.md)
- [../../runbooks/vault-backup-restore.md](../../runbooks/vault-backup-restore.md)
- [../../runbooks/vault-secret-rotation.md](../../runbooks/vault-secret-rotation.md)
- [../../runbooks/vault-auto-unseal.md](../../runbooks/vault-auto-unseal.md)
- [../../runbooks/bootstrap-transit-vault.md](../../runbooks/bootstrap-transit-vault.md)
- [../../runbooks/bootstrap-transit-vault-temporary-trust.md](../../runbooks/bootstrap-transit-vault-temporary-trust.md)
- [../../runbooks/bootstrap-windows-rooted-vault-auto-unseal.md](../../runbooks/bootstrap-windows-rooted-vault-auto-unseal.md)
