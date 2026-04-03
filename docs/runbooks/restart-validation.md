# Restart Validation

## Purpose

Use this runbook after Windows restart, WSL restart, or operator logon to prove
that the full platform came back without hidden manual repair.

For a pure `wsl --shutdown` simulation, the recovery path must come from WSL
`systemd`. A Windows logon task does not re-run in that scenario.

## Required gate

Run:

```bash
make verify-restart-survival
```

This must prove:

- the required bootstrap path for the scenario executed
- WSL `systemd` is running
- `k3s` is enabled and active
- bridge and recovery are enabled, active, and healthy
- Vault pods are present and Vault is unsealed
- core Argo applications are `Synced` and `Healthy`

## Manual checks

If deeper inspection is needed, confirm:

```bash
systemctl is-active k3s openclaw-host-stack.target openclaw-host-bridge.service openclaw-host-recovery.service
curl -fsS http://127.0.0.1:48721/healthz
curl -fsS http://127.0.0.1:48722/healthz
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n vault get pods
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n vault get pods --show-labels
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n argocd get applications.argoproj.io
```

## Current architecture limit

If Vault is using manual Shamir unseal, a normal restart is still an
operator-assisted recovery model.

In that case:

- the verification gate should fail while Vault is sealed
- the platform should not be described as fully restart-survivable
- use [vault-recovery.md](vault-recovery.md) for controlled recovery

## Target state

The target restart-safe design is:

1. Windows bootstrap starts WSL
2. WSL `systemd` starts `k3s` and the host stack after WSL restart
3. WSL `systemd` also triggers the TPM-backed Vault recovery path after `k3s`
   returns
4. External Secrets resyncs
5. Argo applications return to healthy state
6. gateway dependencies are reachable again
