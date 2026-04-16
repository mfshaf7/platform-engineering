# Vault Operations

## Primary Checks

```bash
k3s kubectl -n vault get pods
k3s kubectl -n vault exec vault-0 -- vault status
```

## Common Failure Signals

- Vault pod is running but `vault status` reports sealed
- Vault UI is reachable but logins fail
- External Secrets reports sync failures because upstream secret reads fail
- auto-unseal path stopped working after host or restart changes

## First Response

1. confirm whether the problem is seal state, storage state, auth state, or UI
   reachability
2. verify whether the issue started after a restart, host drift, or bootstrap
   change
3. check whether External Secrets and downstream apps are failing because Vault
   is unavailable, or whether only operator access is broken

## Recovery Sequence

1. inspect pod health and `vault status`
2. verify the intended auto-unseal path and related host/bootstrap state
3. if Vault is sealed, follow the owning recovery or auto-unseal runbook
4. after Vault is healthy, verify External Secrets recovers and dependent apps
   can read secrets again

## Evidence To Capture

Capture:

- `vault status`
- pod state
- whether the instance was sealed or unsealed
- which recovery or auto-unseal path was used
- downstream recovery evidence for External Secrets or dependent apps

## Shared Procedures

- [../../runbooks/bootstrap-vault.md](../../runbooks/bootstrap-vault.md)
- [../../runbooks/vault-recovery.md](../../runbooks/vault-recovery.md)
- [../../runbooks/vault-backup-restore.md](../../runbooks/vault-backup-restore.md)
- [../../runbooks/vault-secret-rotation.md](../../runbooks/vault-secret-rotation.md)
- [../../runbooks/vault-auto-unseal.md](../../runbooks/vault-auto-unseal.md)
- [../../runbooks/bootstrap-transit-vault.md](../../runbooks/bootstrap-transit-vault.md)
- [../../runbooks/bootstrap-transit-vault-temporary-trust.md](../../runbooks/bootstrap-transit-vault-temporary-trust.md)
- [../../runbooks/bootstrap-windows-rooted-vault-auto-unseal.md](../../runbooks/bootstrap-windows-rooted-vault-auto-unseal.md)
