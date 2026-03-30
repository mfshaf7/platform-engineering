# Vault Recovery

## Purpose

This runbook covers immediate recovery actions for Vault initialization,
unseal, and Raft health issues.

## Required Material

- init material file stored at the approved secure location
- unseal keys
- root token or other approved recovery token

## Secure Storage Requirement

The init file and unseal keys must not remain in temporary directories. Keep
them in approved secure storage with access controls and an operator recovery
procedure.

## Check Health

```bash
k3s kubectl -n vault get pods
k3s kubectl -n vault exec vault-0 -- vault status
k3s kubectl -n vault exec vault-1 -- vault status
k3s kubectl -n vault exec vault-2 -- vault status
```

## Unseal A Sealed Pod

Use the threshold number of unseal keys against the sealed pod:

```bash
k3s kubectl -n vault exec vault-0 -- vault operator unseal <key-1>
k3s kubectl -n vault exec vault-0 -- vault operator unseal <key-2>
k3s kubectl -n vault exec vault-0 -- vault operator unseal <key-3>
```

Repeat for each sealed pod.

## Rejoin A Replacement Follower

If a follower loses local Raft state and returns uninitialized:

```bash
k3s kubectl -n vault exec vault-1 -- vault operator raft join http://vault-0.vault-internal:8200
```

Then unseal it with the threshold number of unseal keys.

## Verify Recovery

- one active Vault node and healthy standbys
- `platform-secrets-stage` healthy
- `platform-secrets-prod` healthy
- representative secret reads succeed through External Secrets Operator
