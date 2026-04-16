# ADR-004: Temporary Windows Trust Root For Transit Vault

## Status

Superseded by ADR-005

## Context

The preferred low-cost long-term direction is a separate transit Vault trust
root for workload Vault auto-unseal.

However, a separate transit Vault on the same workstation still needs its own
unseal trust root after a full machine restart. Without that, the restart
problem simply moves from the workload Vault to the transit Vault.

This ADR captured an intermediate design where Windows released secret material
only for a same-host transit Vault.

That design is no longer the temporary implementation target because same-host
WSL distro separation did not provide a reliable trust and network boundary for
the transit endpoint on this workstation.

For the current workstation budget and architecture constraints, the platform
still needs a temporary trust model that:

- keeps workload Vault unseal separate from the main platform runtime
- avoids storing raw workload unseal material in startup scripts
- allows the transit trust root to recover automatically after Windows restart

## Decision

The temporary trust chain will be:

- Windows protected secret storage
  -> transit Vault unseal path
  -> workload Vault transit auto-unseal

In practical terms:

- Windows is the temporary local trust root
- `Platform-Transit` hosts the dedicated transit Vault
- `Platform-Core` hosts the workload Vault and the rest of the platform

The preferred Windows protection mechanism is TPM-backed key protection with
DPAPI or Credential Manager layered on top as needed by the implementation.

## Why This Decision

### Better than direct workload unseal on the host

Using Windows to release unseal material only for the transit Vault preserves a
cleaner split than making the workload Vault depend directly on host-stored
unseal credentials.

### Stronger than DPAPI-only when TPM is available

If the workstation exposes a usable TPM, the temporary trust root should bind
the transit-unseal release path to TPM-backed key material rather than relying
on account-scoped DPAPI alone.

### Honest temporary model

This ADR does not pretend to be equivalent to cloud KMS, HSM, or a genuinely
external transit trust root.

It is explicitly a workstation-trust-rooted temporary model.

## Consequences

### Positive

- enables full-machine restart automation on a local budget
- keeps workload Vault behind a separate transit boundary
- fits the existing Windows bootstrap ownership model

### Negative

- Windows becomes the temporary root of trust
- a workstation compromise can compromise the transit unseal path
- this model must not be described as equivalent to enterprise external KMS
- TPM availability and Windows key-protection behavior now become part of the
  local platform dependency set

## Guardrails

- do not store plaintext unseal material in Git
- do not store plaintext unseal material in permanent startup scripts
- restrict the Windows-released secret to the transit Vault only
- keep the workload Vault dependent on transit, not on direct host unseal
- prefer TPM-backed release over DPAPI-only release when the machine supports it
- record the eventual migration away from this model when a stronger external
  trust root exists

## Replacement target

This ADR is temporary by design.

The replacement target is:

- external KMS-backed transit or direct auto-unseal, or
- a stronger separately operated transit trust root
