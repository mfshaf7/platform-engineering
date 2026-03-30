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

- Argo CD username: `admin`
- Argo CD password: retrieve from `argocd-initial-admin-secret` or rotate it
  after bootstrap
- Grafana username: `mfshaf7`
- Grafana password: Vault-backed and synced through External Secrets

Notes:

- Argo CD uses a self-signed certificate by default on the local cluster, so
  the browser will show a certificate warning until you replace it.
- Vault is intentionally exposed over local HTTP because the in-cluster chart
  is running with `tlsDisable: true`; keep it on localhost only unless you add
  TLS.
