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
- `platform-vault-unseal.service` is enabled and active when unattended Vault recovery is configured
- Vault pods are present and Vault is unsealed
- core Argo applications are `Synced` and `Healthy`
- Windows localhost Ollama on `127.0.0.1:11434` is reachable
- live gateway pods can reach `http://host.docker.internal:11434/api/tags`

## Manual checks

If deeper inspection is needed, confirm:

```bash
systemctl is-active k3s openclaw-host-stack.target openclaw-host-bridge.service openclaw-host-recovery.service platform-vault-unseal.service
curl -fsS http://127.0.0.1:48721/healthz
curl -fsS http://127.0.0.1:48722/healthz
powershell.exe -NoProfile -Command "Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 5 | Select-Object -ExpandProperty StatusCode"
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n vault get pods
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n vault get pods --show-labels
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n argocd get applications.argoproj.io
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n openclaw exec deploy/openclaw-gateway -- sh -lc 'wget -qO- --timeout=5 http://host.docker.internal:11434/api/tags | head -c 120'
KUBECONFIG=/etc/rancher/k3s/k3s.yaml /usr/local/bin/k3s kubectl -n openclaw-stage exec deploy/openclaw-gateway -- sh -lc 'wget -qO- --timeout=5 http://host.docker.internal:11434/api/tags | head -c 120'
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
6. gateway dependencies, including the Ollama forward path, are reachable again
