# ADR-003: Separate Transit Vault For Auto-Unseal

## Status

Accepted

## Context

The local platform currently uses a single HA Raft Vault cluster with manual
Shamir unseal.

That means:

- Vault can remain sealed after restart
- External Secrets cannot sync while Vault is sealed
- restart recovery is operator-assisted rather than unattended

The platform needs a low-cost path to unattended restart recovery without
introducing paid cloud KMS dependencies.

## Decision

The preferred low-cost auto-unseal model is a separate transit Vault trust
root.

The design is:

- the existing in-cluster Vault remains the workload and secret-delivery Vault
- a second Vault instance acts only as the transit auto-unseal trust root
- the workload Vault uses `seal "transit"` against that second Vault
- the transit Vault must not run in the same Kubernetes cluster as the workload
  Vault

For this workstation-oriented platform, the preferred placement is:

- a separate WSL distro dedicated to transit Vault
- no product workloads on that distro
- its own persistent storage and operator lifecycle

## Why This Decision

### Preferred over local secret release

Using Windows DPAPI, Credential Manager, or plaintext startup material would
automate restart recovery, but it would collapse the unseal trust boundary into
the workstation host.

Transit auto-unseal preserves a more meaningful separation between:

- host/workstation bootstrap
- platform workload Vault
- unseal trust root

### Preferred over same-cluster transit Vault

Running the transit Vault inside the same cluster would reduce operational value
and create circular dependency risk.

The unseal trust root must remain available when the workload cluster is
recovering.

## Consequences

### Positive

- removes routine manual unseal from restart recovery
- improves restart-survival without paid KMS
- keeps raw unseal keys out of normal startup automation

### Negative

- introduces a second critical Vault service to operate
- increases bootstrap and disaster-recovery complexity
- still does not equal external KMS if both systems remain on the same physical
  workstation

## Transit availability modes

Two operating modes are allowed:

### Warm transit trust root

- the transit Vault is left running
- workload Vault can auto-unseal during routine restart without operator action
- this is the required mode for a true unattended restart-survival claim

### Cold transit trust root

- the transit Vault distro is brought online only for unseal windows
- workload Vault can auto-unseal only while the transit Vault is reachable
- the transit Vault may be stopped again after the workload Vault is fully
  unsealed

This cold mode is operationally valid, but it is not a full unattended restart
model. It is an assisted auto-unseal model.

## Guardrails

- the transit Vault must be documented as a separate trust root
- the transit Vault must not host product runtime secrets
- the workload Vault must fail restart-survival verification if the transit
  dependency is unavailable
- restart survival claims remain invalid until the design is actually deployed
  and verified
