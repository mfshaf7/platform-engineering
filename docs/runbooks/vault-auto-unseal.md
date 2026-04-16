# Vault Auto-Unseal

## Purpose

This runbook defines the target path for moving the platform from manual Vault
recovery to unattended restart survival.

## Problem

The current local platform uses Shamir recovery keys for Vault unseal.

That means:

- Vault may remain sealed after a routine restart
- External Secrets cannot sync while Vault is sealed
- Argo-managed secret consumers remain degraded
- the platform requires operator intervention before it is fully back

## Decision rule

Use one of these models explicitly:

### Operator-assisted model

Acceptable when:

- this platform is treated as a local operator-managed environment
- routine restart may require manual recovery
- restart survival is not claimed as unattended

### Unattended restart model

Required when:

- the platform should recover normally after restart
- the cluster and workloads are expected to return without manual intervention

This model requires auto-unseal or an equivalent trusted unseal mechanism.

## Recommended target

Preferred order:

1. cloud KMS-backed auto-unseal
2. HSM-backed auto-unseal
3. Vault Transit auto-unseal using a separately managed trust root
4. Windows-rooted TPM-backed temporary auto-unseal

For this local platform, the current temporary implementation target is option
`4`, using Windows as the workstation trust root with TPM-backed protection for
the Vault bootstrap secret. See
[ADR-005-windows-rooted-tpm-backed-vault-auto-unseal.md](../decisions/adr/ADR-005-windows-rooted-tpm-backed-vault-auto-unseal.md)
and [bootstrap-windows-rooted-vault-auto-unseal.md](bootstrap-windows-rooted-vault-auto-unseal.md).

The separate transit Vault path remains the preferred low-cost architecture
when the transit trust root can run on a genuinely separate boundary. See
[ADR-003-vault-transit-auto-unseal.md](../decisions/adr/ADR-003-vault-transit-auto-unseal.md)
and [bootstrap-transit-vault.md](bootstrap-transit-vault.md).

Do not treat a second WSL distro on the same workstation as a sufficient
network trust boundary for transit unless that separation has been explicitly
verified for the active WSL networking mode.

When the workstation exposes a usable TPM, prefer TPM-backed Windows protection
over DPAPI-only storage.

Do not store unseal material in Git, local startup scripts, or plaintext host
files just to simulate unattended recovery.

## Governance requirement

Before enabling auto-unseal in production-like use:

- document the chosen trust root
- document credential ownership and rotation
- record the bootstrap and recovery process
- add restart validation evidence through `make verify-restart-survival`

## Minimum rollout plan

1. choose the trusted auto-unseal backend
2. document the required platform credentials outside the repo
3. update the shared Vault deployment values and bootstrap runbook
4. reinitialize or migrate Vault as required by the chosen backend
5. perform a controlled restart test
6. record the result in a change record
