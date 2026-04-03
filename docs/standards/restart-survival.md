# Restart Survival Standard

## Purpose

This standard defines when the local platform may be called restart-survivable.

The goal is to prevent a partial recovery state where Windows, WSL, or `k3s`
come back, but the actual platform still depends on manual operator repair.

## Core rule

The platform is restart-survivable only when a normal host restart or logon can
restore the full managed stack without ad hoc operator intervention.

That includes:

- Windows bootstrap
- WSL `systemd`
- host bridge and recovery services
- `k3s`
- Vault availability
- External Secrets delivery
- Argo-managed workloads
- gateway dependency reachability required for normal operation

## Required post-restart outcome

After a normal restart or logon:

1. the Windows bootstrap path starts the WSL-managed host stack
2. `k3s` is active and the node is `Ready`
3. bridge and recovery are active and answer health checks
4. Vault is available for runtime secret delivery
5. Vault-backed secrets reconcile without manual repair
6. core Argo applications return to `Synced` and `Healthy`
7. the gateway path can reach its required host-side dependencies

If any one of those steps still depends on a manual operator action, the
platform is not fully restart-survivable.

## Manual Vault unseal rule

Manual Shamir unseal is a controlled recovery model, not an unattended restart
model.

If Vault requires manual unseal after a routine restart, the platform may be
described as operator-assisted but must not be described as fully
restart-survivable.

## Allowed resilience classes

### Operator-assisted local platform

Allowed when:

- restarts are expected to need operator action
- the recovery path is documented
- the verification gate is re-run after recovery

### Unattended resilient platform

Required when:

- routine restart should restore service automatically
- production-like operation depends on unattended recovery

This class requires auto-unseal or an equivalent trusted unseal mechanism for
Vault.

For this local platform, the preferred low-cost target is a separate transit
Vault trust root rather than host-stored unseal material.

If the transit trust root is intentionally offline except during unseal
windows, the platform remains assisted rather than fully unattended.

## Verification gate

The required verification gate is:

```bash
make verify-restart-survival
```

The gate must fail if:

- `k3s` is inactive
- bridge or recovery is inactive or unhealthy
- Vault is sealed
- core Argo applications are not `Synced` and `Healthy`

## Governance rule

A restart-survival claim is only valid when it is backed by:

- source-controlled bootstrap assets
- runbook-defined recovery steps
- an executable verification gate
- change records for any recurring drift or resilience repair
