# Restart Survival Standard

## Purpose

This standard defines when the local platform may be called restart-survivable.

The goal is to prevent a partial recovery state where Windows, WSL, or `k3s`
come back, but the actual platform still depends on manual operator repair.

## Core rule

The platform is restart-survivable only when a normal host restart or logon can
restore the full managed stack without ad hoc operator intervention.

That includes, depending on the restart type:

- Windows bootstrap when Windows actually restarted or the user logged on
- WSL `systemd` bootstrap when only the WSL distro restarted
- WSL `systemd`
- host bridge and recovery services
- `k3s`
- Vault availability
- External Secrets delivery
- Argo-managed workloads
- gateway dependency reachability required for normal operation

## Required post-restart outcome

After a normal restart, WSL restart, or logon:

1. the correct bootstrap path for the event starts the WSL-managed host stack
2. `k3s` is active and the node is `Ready`
3. bridge and recovery are active and answer health checks
4. Vault is available for runtime secret delivery without ad hoc manual unseal
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

For this local platform, the current temporary unattended target is a
Windows-rooted TPM-backed recovery path rather than same-host WSL transit
indirection.

If the platform uses Windows-protected storage to recover Vault, document that
explicitly as a workstation-trust-rooted temporary model rather than a final
external-trust-root solution.

When TPM is available on the workstation, prefer TPM-backed protection for that
temporary Windows trust root.

If a future transit trust root is introduced, it must run on a genuinely
separate boundary rather than relying on same-host WSL distro separation alone.

## Verification gate

The required verification gate is:

```bash
make verify-restart-survival
```

The gate must fail if:

- `k3s` is inactive
- bridge or recovery is inactive or unhealthy
- the WSL Vault unseal service is not enabled and active when unattended unseal is configured
- Vault is sealed
- core Argo applications are not `Synced` and `Healthy`
- Windows localhost Ollama is unreachable on `127.0.0.1:11434`
- a live gateway pod cannot reach `http://host.docker.internal:11434/api/tags`

## Governance rule

A restart-survival claim is only valid when it is backed by:

- source-controlled bootstrap assets
- runbook-defined recovery steps
- an executable verification gate
- change records for any recurring drift or resilience repair
