# ADR-004: Temporary Windows Trust Root For Transit Vault

## Status

Accepted

## Context

The preferred low-cost long-term direction is a separate transit Vault trust
root for workload Vault auto-unseal.

However, a separate transit Vault on the same workstation still needs its own
unseal trust root after a full machine restart. Without that, the restart
problem simply moves from the workload Vault to the transit Vault.

For the current workstation budget and architecture constraints, the platform
needs a temporary trust model that:

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

The preferred Windows protection mechanism is DPAPI-backed secret storage.

## Why This Decision

### Better than direct workload unseal on the host

Using Windows to release unseal material only for the transit Vault preserves a
cleaner split than making the workload Vault depend directly on host-stored
unseal credentials.

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

## Guardrails

- do not store plaintext unseal material in Git
- do not store plaintext unseal material in permanent startup scripts
- restrict the Windows-released secret to the transit Vault only
- keep the workload Vault dependent on transit, not on direct host unseal
- record the eventual migration away from this model when a stronger external
  trust root exists

## Replacement target

This ADR is temporary by design.

The replacement target is:

- external KMS-backed transit or direct auto-unseal, or
- a stronger separately operated transit trust root
