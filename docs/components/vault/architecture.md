# Vault Architecture

## Role

Vault is the shared secret source of truth for the platform.

It owns:

- operator secret workflows
- secret storage for shared platform services
- secret storage for product runtime credentials
- the current cluster-side secret source consumed by External Secrets

## Current Live Shape

- namespace: `vault`
- Argo application: `vault`
- current UI/API service: `vault-ui`

## Model

The current platform uses an in-cluster Vault as the workload and secret
delivery store.

Auto-unseal and recovery posture are governed by these ADRs:

- [../../decisions/adr/ADR-003-vault-transit-auto-unseal.md](../../decisions/adr/ADR-003-vault-transit-auto-unseal.md)
- [../../decisions/adr/ADR-004-transit-vault-temporary-windows-trust-root.md](../../decisions/adr/ADR-004-transit-vault-temporary-windows-trust-root.md)
- [../../decisions/adr/ADR-005-windows-rooted-tpm-backed-vault-auto-unseal.md](../../decisions/adr/ADR-005-windows-rooted-tpm-backed-vault-auto-unseal.md)

## Read With

- [../../architecture/overview.md](../../architecture/overview.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
