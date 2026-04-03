# Bootstrap Windows-Rooted Vault Auto-Unseal

## Purpose

This runbook defines the temporary workstation-trust-rooted path for unattended
Vault recovery using Windows bootstrap and TPM-backed protected secret release.

## Scope

Use this model when:

- the platform runs on a single Windows workstation
- restart recovery should be unattended
- cloud KMS or a real separate transit trust root is not available yet

Do not describe this model as equivalent to external KMS or HSM-backed
auto-unseal.

## Target chain

- Windows scheduled-task bootstrap starts
- Windows releases TPM-backed protected secret material
- Windows bootstraps workload Vault unseal
- `make verify-restart-survival` confirms platform recovery

## Requirements

- Windows TPM present and ready
- governed Windows bootstrap path already in place
- encrypted recovery material stored outside Git
- recovery steps recorded in the platform change record set

## Guardrails

- do not commit unseal material or bootstrap secrets into Git
- do not leave decrypted recovery material on disk after bootstrap
- keep the Windows bootstrap path source-controlled and reproducible
- finish the bootstrap by running the restart-survival verification gate

## Verification

The required gate remains:

```bash
make verify-restart-survival
```

The platform must not be called restart-survivable unless that gate passes
after the Windows-rooted bootstrap path runs.
