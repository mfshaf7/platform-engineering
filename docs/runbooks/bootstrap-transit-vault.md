# Bootstrap Transit Vault

## Purpose

This runbook defines the target low-cost path for unattended Vault unseal using
a separate transit Vault trust root.

## Scope

This runbook does not bootstrap the workload Vault in Kubernetes. It bootstraps
the separate trust-root Vault that exists only to provide transit auto-unseal.

For the temporary workstation-trust-rooted model, also use
[bootstrap-transit-vault-temporary-trust.md](bootstrap-transit-vault-temporary-trust.md).

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

## Provisioning path

Clone `platform-engineering` inside the dedicated `Platform-Transit` distro and
run:

```bash
make provision-transit-vault-host
```

This installs the minimal single-purpose transit Vault service and its systemd
unit inside that distro.

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

## Temporary workstation orchestration

The platform bootstrap can support a temporary workstation-oriented transit
sequence through the generated Windows bootstrap artifact.

Supported modes:

- `disabled`
  - current default
  - no transit orchestration is attempted
- `warm`
  - Windows bootstrap starts the transit distro and leaves transit Vault
    running
- `cold`
  - Windows bootstrap starts the transit distro, waits for transit Vault
    health, starts `Platform-Core`, waits for workload Vault to report
    unsealed, then stops the transit Vault service again

This keeps the orchestration under the existing governed Windows bootstrap path
instead of introducing a separate ad hoc startup script.

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

For this workstation-oriented path, the workload Vault should eventually target
the managed Windows-forwarded transit endpoint on:

```text
http://host.docker.internal:18200
```

The generated Windows bootstrap now owns that portproxy when transit
orchestration is enabled.

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

## Availability modes

### Warm mode

Keep the `Platform-Transit` distro running continuously.

Use this mode if you want:

- unattended workload Vault restart recovery
- the ability for Vault pods to restart and auto-unseal at any time

### Cold mode

Bring `Platform-Transit` online only during the workload Vault unseal window,
then stop it again after the workload cluster is fully up.

This is possible because the workload Vault only needs the transit trust root
while performing auto-unseal.

However:

- if workload Vault restarts again while transit is offline, auto-unseal will
  fail until transit is brought back
- this mode does not satisfy a strict unattended restart-survival claim
- this mode should be described as assisted auto-unseal, not full automatic
  recovery

## Recommended use

For this workstation platform:

- use `warm` mode if you want genuine unattended restart recovery
- use `cold` mode if you want stronger trust separation while accepting that
  restart recovery still depends on bringing the transit distro online first

## Verification

Success means:

- workload Vault comes back unsealed after restart
- External Secrets resyncs without manual recovery
- `make verify-restart-survival` passes

## Current state

This topology is the accepted target design. It is not yet deployed by this
repository.

The generated bootstrap now supports transit orchestration, but it remains
disabled by default until a real `Platform-Transit` distro and transit Vault
exist.
