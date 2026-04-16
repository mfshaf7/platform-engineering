# ADR-005: Windows-Rooted TPM-Backed Temporary Vault Auto-Unseal

## Status

Accepted

## Context

The preferred long-term direction remains an external trust root such as cloud
KMS, HSM, or a separately operated transit Vault.

However, the local workstation needs an unattended restart path now, and the
same-host `Platform-Transit` WSL design did not provide a reliable trust and
network boundary. In the active WSL topology, separate distros did not behave
like independently reachable hosts, which made the transit endpoint unstable
from the workload side.

That means the platform needs a temporary restart-survival model that:

- works on the current workstation
- does not depend on paid cloud services
- remains honest about Windows being the effective local root of trust

## Decision

The temporary unattended restart model will be:

- Windows startup/bootstrap
  -> TPM-backed protected secret release
  -> Vault auto-unseal bootstrap
  -> `make verify-restart-survival`

In practical terms:

- Windows is the temporary local trust root
- TPM-backed protection is preferred for the released secret material
- the workload Vault is recovered directly through the governed Windows
  bootstrap path instead of through a same-host WSL transit boundary

## Why This Decision

### Works with the real host boundary

Windows already owns the lifecycle of WSL startup and scheduled-task bootstrap.
Using it as the temporary trust root matches the actual control plane instead
of inventing a stronger separation than the host provides.

### Stronger than DPAPI-only storage

If the workstation exposes a usable TPM, the release path should be bound to
TPM-backed key material rather than relying on account-scoped DPAPI alone.

### More honest than same-host pseudo-separation

On this workstation, a second WSL distro did not provide a stable independent
transit endpoint. Treating it as a trustworthy separate network boundary would
have been misleading.

## Consequences

### Positive

- enables unattended restart recovery on the current host
- avoids paid infrastructure for the temporary model
- keeps recovery under the existing governed Windows bootstrap path

### Negative

- Windows becomes the temporary root of trust
- a workstation compromise can compromise the unseal path
- this is not equivalent to external KMS, HSM, or a real separate transit host

## Guardrails

- do not store plaintext unseal material in Git
- do not store plaintext unseal material in permanent startup scripts
- prefer TPM-backed release over DPAPI-only release when available
- keep the bootstrap and verification path in source control
- record the eventual migration away from this model when a stronger external
  trust root exists

## Replacement target

This ADR is temporary by design.

The replacement target is:

- external KMS-backed auto-unseal, or
- a genuinely separate transit trust root such as a dedicated VM or external
  service
