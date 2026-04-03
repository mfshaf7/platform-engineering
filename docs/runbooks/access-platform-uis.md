# Access Platform UIs

The local Platform-Core host exposes the main operator surfaces on Windows
localhost through stable NodePorts plus the managed Windows portproxy refresh.

Endpoints:

- Argo CD: `https://127.0.0.1:32443`
- Vault UI: `http://127.0.0.1:32200`
- Prometheus prod: `http://127.0.0.1:32090`
- Prometheus stage: `http://127.0.0.1:32091`
- Alertmanager prod: `http://127.0.0.1:32093`
- Alertmanager stage: `http://127.0.0.1:32094`
- Grafana prod: `http://127.0.0.1:32080`
- Grafana stage: `http://127.0.0.1:32081`

Current credentials:

- Operator usernames and passwords must not be stored in Git-tracked docs.
- Retrieve the current operator username from your platform secret manager or
  local operator credential handoff.
- If operator access must be reissued, run
  [bootstrap_operator_access.sh](../../scripts/bootstrap_operator_access.sh)
  with a freshly chosen password, then update the live secret sources outside
  the repo.

Notes:

- Argo CD uses a self-signed certificate by default on the local cluster, so
  the browser will show a certificate warning until you replace it.
- Vault is intentionally exposed over local HTTP because the in-cluster chart
  is running with `tlsDisable: true`; keep it on localhost only unless you add
  TLS.
- Argo CD and Vault operator credentials are bootstrapped by
  [bootstrap_operator_access.sh](../../scripts/bootstrap_operator_access.sh),
  not by a Git-tracked static secret.
- Prometheus, Alertmanager, and Grafana operator auth must be sourced from
  Vault-backed cluster secrets, not hard-coded in this runbook.
- Host-side Ollama access for the gateway is refreshed by the managed Windows
  bootstrap path. It forwards the WSL-resolved `host.docker.internal:11434`
  address to Windows `127.0.0.1:11434`, so the gateway can keep using the
  OpenClaw config's Ollama base URL after restarts.
