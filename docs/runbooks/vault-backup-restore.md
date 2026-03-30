# Vault Backup And Restore

## Purpose

This runbook defines the minimum operator workflow for backing up and restoring
the platform Vault cluster.

## Scope

- Vault runs as a Raft-backed HA cluster in the `vault` namespace
- product runtime secrets are stored under `products/<product>/<environment>/...`
- External Secrets Operator consumes Vault as the source of truth

## Backup Policy

- take regular raft snapshots from the active Vault node
- store snapshots outside the cluster
- protect snapshots with the same sensitivity as live secret material
- verify restore on a controlled schedule

## Create A Snapshot

1. obtain the current Vault root or recovery-capable operator token
2. run from the host:

```bash
export VAULT_TOKEN='...'
k3s kubectl -n vault exec vault-0 -- \
  env VAULT_TOKEN="$VAULT_TOKEN" \
  vault operator raft snapshot save /tmp/platform-vault.snap
k3s kubectl -n vault cp vault/vault-0:/tmp/platform-vault.snap ./platform-vault.snap
```

3. move `platform-vault.snap` into approved secure storage

## Restore Principles

- restore into a controlled outage window
- keep the current init material and recovery documentation available
- restore the Raft snapshot before re-enabling dependent secret consumers

## Restore Flow

1. scale down or pause workloads that depend on Vault-backed secrets if needed
2. copy the approved snapshot to the active Vault pod
3. run:

```bash
export VAULT_TOKEN='...'
k3s kubectl -n vault cp ./platform-vault.snap vault/vault-0:/tmp/platform-vault.snap
k3s kubectl -n vault exec vault-0 -- \
  env VAULT_TOKEN="$VAULT_TOKEN" \
  vault operator raft snapshot restore -force /tmp/platform-vault.snap
```

4. verify Vault health and Raft peer state
5. verify `platform-secrets-stage` and `platform-secrets-prod` return to
   `Healthy`

## Post-Restore Verification

- `k3s kubectl -n vault get pods`
- `k3s kubectl -n argocd get applications.argoproj.io vault platform-secrets-stage platform-secrets-prod`
- validate a representative secret path and runtime health endpoint
