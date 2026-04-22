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
```

## Unseal The Workload Pod

Use the threshold number of unseal keys against the sealed workload pod:

```bash
k3s kubectl -n vault exec vault-0 -- vault operator unseal <key-1>
k3s kubectl -n vault exec vault-0 -- vault operator unseal <key-2>
k3s kubectl -n vault exec vault-0 -- vault operator unseal <key-3>
```

There is no in-cluster follower rejoin flow in the current single-node posture.
If the lone pod loses local Raft state, recover from the approved snapshot and
re-bootstrap the pod rather than attempting a peer join.

## Verify Recovery

- `vault-0` healthy and unsealed
- `platform-secrets-stage` healthy
- `platform-secrets-prod` healthy
- representative secret reads succeed through External Secrets Operator
