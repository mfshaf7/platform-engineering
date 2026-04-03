# Bootstrap Transit Vault With Temporary Windows Trust Root

## Purpose

This runbook defines the temporary fully automated workstation path:

- Windows protected secret storage
- `Platform-Transit` dedicated transit Vault
- `Platform-Core` workload Vault using `seal "transit"`

## Scope

This runbook is the temporary local-budget model only.

It is not the final enterprise-grade trust-root design.

## Trust chain

The temporary trust chain is:

1. Windows logon/startup bootstrap runs
2. Windows releases a TPM/DPAPI-protected secret for the transit Vault only
3. `Platform-Transit` starts and unseals transit Vault
4. `Platform-Core` starts
5. workload Vault auto-unseals through transit
6. `make verify-restart-survival` runs

## Required boundary

Windows may help unseal transit Vault.

Windows must not directly unseal the workload Vault.

That boundary is what keeps the temporary model cleaner than a direct
host-to-workload unseal shortcut.

## Required implementation pieces

1. a clean `Platform-Transit` distro
2. transit Vault service provisioned there
3. transit Vault initialized and configured with the transit secrets engine
4. workload Vault configured with `seal "transit"`
5. Windows bootstrap that can:
   - start `Platform-Transit`
   - release the protected transit-only secret
   - trigger transit Vault unseal
   - start `Platform-Core`
   - verify restart survival

## Secret-handling rule

Use Windows protected storage only for the transit Vault unseal path.

Preferred order:

1. TPM-backed Windows key protection
2. DPAPI-backed Windows protection
3. Credential Manager only as a wrapper around one of the above

Do not:

- store plaintext recovery keys in Git
- place plaintext unseal keys in scheduled-task arguments
- reuse the same host secret as a direct workload Vault unseal credential

## Platform note

This workstation currently reports a usable TPM. That makes TPM-backed
protection the preferred temporary implementation rather than plain DPAPI-only
release.

## Operational modes

### Warm transit

- transit Vault stays online
- best fit for unattended restart recovery

### Cold transit

- transit Vault is started only for the unseal window
- can still support automated startup if Windows starts and unseals it first
- may be stopped again after the workload Vault is confirmed unsealed

## Verification

The platform is only considered recovered when:

```bash
make verify-restart-survival
```

passes after the automated chain completes.

## Migration note

This model should remain clearly labeled as temporary until replaced by a
stronger external trust root.
