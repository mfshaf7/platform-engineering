# External Secrets Architecture

## Role

External Secrets Operator is the shared bridge between Vault and Kubernetes
secrets.

It owns:

- reading approved secret material from the configured store
- materializing Kubernetes secrets for workloads
- keeping runtime secrets out of Git

## Current Live Shape

- namespace: `external-secrets`
- Argo application: `external-secrets`

## Model

The current platform model is:

- Vault is the secret source of truth
- External Secrets syncs approved secrets into Kubernetes
- workloads consume Kubernetes secrets without embedding credential material in
  Git

## Read With

- [../../architecture/overview.md](../../architecture/overview.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
- [../../standards/secrets.md](../../standards/secrets.md)
