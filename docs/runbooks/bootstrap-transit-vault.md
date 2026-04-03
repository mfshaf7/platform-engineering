# Bootstrap Transit Vault

## Purpose

This runbook defines the target low-cost path for unattended Vault unseal using
a separate transit Vault trust root.

## Scope

This runbook does not bootstrap the workload Vault in Kubernetes. It bootstraps
the separate trust-root Vault that exists only to provide transit auto-unseal.

## Target topology

- workload Vault:
  - runs in the `vault` namespace inside the local `k3s` cluster
  - stores platform and product runtime secrets
- transit Vault:
  - runs outside the workload cluster
  - should live in a separate WSL distro such as `Platform-Transit`
  - should not host product workloads
  - should expose only the minimal API surface required for transit auto-unseal

## Prerequisites

- a separate WSL distro exists for the transit Vault
- `systemd` is enabled in that distro
- Vault binary or package is installed in that distro
- persistent storage exists for the transit Vault data path
- a narrow network path exists from the workload Vault pods to the transit Vault

## Required security model

- transit Vault is a trust root, not an app runtime
- store only transit auto-unseal material there
- keep operator recovery material outside Git
- use a tightly scoped token or AppRole for workload Vault auto-unseal

## High-level sequence

1. bootstrap the separate WSL distro
2. install and start transit Vault in that distro
3. initialize and unseal transit Vault once
4. enable the transit secrets engine
5. create a dedicated transit key for workload Vault unseal
6. create a least-privilege policy allowing only the transit operations needed
   for auto-unseal
7. create a dedicated token or AppRole for the workload Vault
8. update the workload Vault Helm configuration with a `seal "transit"` stanza
9. restart workload Vault in a controlled window
10. verify `make verify-restart-survival` passes without manual unseal

## Example workload Vault configuration shape

The workload Vault Helm values will eventually need a `seal "transit"` stanza
inside the HA config, conceptually like this:

```hcl
seal "transit" {
  address            = "http://<transit-vault-address>:8200"
  token              = "<workload-auto-unseal-token>"
  disable_renewal    = "false"
  key_name           = "platform-vault-unseal"
  mount_path         = "transit/"
  tls_skip_verify    = "true"
}
```

Do not commit the real token into Git. The workload Vault must receive that
credential through an approved secret-delivery path.

## Recommended local placement

For this platform, the recommended minimum-separation placement is:

- workload platform:
  - `Platform-Core`
  - `k3s`, Argo, workload Vault, gateway, observability
- transit trust root:
  - `Platform-Transit`
  - dedicated Vault only

This is still one physical workstation, but it is better than collapsing the
unseal root into the same distro and cluster.

## Verification

Success means:

- workload Vault comes back unsealed after restart
- External Secrets resyncs without manual recovery
- `make verify-restart-survival` passes

## Current state

This topology is the accepted target design. It is not yet deployed by this
repository.
