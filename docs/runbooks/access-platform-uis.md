# Access Platform UIs

## Purpose

This runbook defines the current operator access paths for the shared platform
and the currently integrated products.

It is an observed operator-access surface for the current live environment, not the target steady-state architecture.

This is the practical companion to
[../architecture/current-platform-topology.md](../architecture/current-platform-topology.md).

Last access verification update: `2026-04-19`.

## Supported Access Model

The supported human-operator path is Windows localhost, refreshed by the
managed `PlatformCoreHostStack` bootstrap path.

Important clarification:

- `127.0.0.1:<port>` in this runbook is the Windows operator path
- a WSL shell should not assume that the same localhost port is reachable from
  inside WSL
- when you need a shell-local endpoint from WSL, use the `k3s kubectl
  port-forward` fallback shown below

## Current Access Matrix

| Surface | Current state | Supported Windows/operator URL | WSL shell fallback | Credential source |
| --- | --- | --- | --- | --- |
| Argo CD | Live | `https://127.0.0.1:32443` | `k3s kubectl -n argocd port-forward svc/argocd-server 8443:443` | Operator account provisioned by [bootstrap_operator_access.sh](../../scripts/bootstrap_operator_access.sh) |
| Vault UI and API | Live | `http://127.0.0.1:32200` | `k3s kubectl -n vault port-forward svc/vault-ui 8220:8200` | Same operator username/password model provisioned by [bootstrap_operator_access.sh](../../scripts/bootstrap_operator_access.sh) |
| Platform Grafana prod | Live | `http://127.0.0.1:32080` | `k3s kubectl -n observability port-forward svc/platform-observability-prod-grafana 3000:80` | Vault path `kv/platform/observability/prod/grafana-admin` |
| Platform Prometheus prod | Live | `http://127.0.0.1:32090` | `k3s kubectl -n observability port-forward svc/platform-operator-ui-auth-proxy 9090:9090` | Vault path `kv/platform/observability/prod/operator-ui-auth` |
| Platform Alertmanager prod | Live | `http://127.0.0.1:32093` | `k3s kubectl -n observability port-forward svc/platform-operator-ui-auth-proxy 9093:9093` | Vault path `kv/platform/observability/prod/operator-ui-auth` |
| OpenProject | Live | `http://127.0.0.1:32083` | `k3s kubectl -n openproject port-forward svc/openproject 8080:8080` | Vault path `kv/products/openproject/prod/admin` |
| OpenClaw prod | Suspended by the governed prod lifecycle | no browser UI while suspended | return prod to `live`, then use `k3s kubectl -n openclaw port-forward svc/openclaw-gateway 18789:18789` | no shared browser login; use product-specific runtime surface and Telegram |
| Platform Grafana stage | Not currently live | `http://127.0.0.1:32081` only when stage observability is resumed | resume stage, then use `k3s kubectl -n observability-stage port-forward svc/platform-observability-stage-grafana 3001:80` | Vault path `kv/platform/observability/stage/grafana-admin` |
| Platform Prometheus stage | Not currently live | `http://127.0.0.1:32091` only when stage observability is resumed | resume stage, then use `k3s kubectl -n observability-stage port-forward svc/platform-operator-ui-auth-proxy 9091:9090` | Vault path `kv/platform/observability/stage/operator-ui-auth` |
| Platform Alertmanager stage | Not currently live | `http://127.0.0.1:32094` only when stage observability is resumed | resume stage, then use `k3s kubectl -n observability-stage port-forward svc/platform-operator-ui-auth-proxy 9094:9093` | Vault path `kv/platform/observability/stage/operator-ui-auth` |
| OpenClaw stage | Live for the current stabilization window | no browser UI; primary live user path is Telegram | `k3s kubectl -n openclaw-stage port-forward svc/openclaw-gateway 28789:18789` | no shared browser login; use product-specific runtime surface and Telegram |

## What Is Not Directly Exposed

These are intentionally not documented as direct operator UIs:

- `platform-postgresql`
  - internal-only cluster service
- External Secrets Operator
  - controller only, no UI
- `operator-orchestration-service`
  - internal-only shared broker service, no shared browser UI
- OpenClaw gateway
  - health and runtime API surface only, not an end-user browser application

## Observability Identity Note

Grafana, Prometheus, and Alertmanager in this matrix are shared platform
baseline surfaces. Their runtime identities are now platform-owned as:

- `platform-observability-prod`
- `platform-observability-stage`

## Credential Notes

- Do not store operator usernames, passwords, or tokens in Git-tracked docs.
- Argo CD and Vault operator access are intentionally provisioned together by
  [bootstrap_operator_access.sh](../../scripts/bootstrap_operator_access.sh).
- Grafana admin credentials and operator auth-proxy credentials are sourced
  from Vault-backed External Secrets, not from Git.
- OpenProject admin credentials come from Vault path
  `kv/products/openproject/prod/admin`.

## Reissue Operator Access

If Argo CD or Vault operator access must be reissued:

1. obtain a current recovery-capable Vault token
2. choose a fresh operator username and password
3. run:

```bash
export VAULT_TOKEN='<current-vault-token>'
export OPERATOR_USERNAME='<new-operator-username>'
export OPERATOR_PASSWORD='<new-operator-password>'
./scripts/bootstrap_operator_access.sh
```

This provisions the Vault userpass account and the matching Argo CD operator
account without storing the credential in Git.

## Quick Inventory Commands

```bash
k3s kubectl -n argocd get applications
k3s kubectl get svc -A
python3 products/openclaw/scripts/set_prod_environment_state.py status
python3 products/openclaw/scripts/set_stage_environment_state.py status
```

For OpenClaw stage, treat that status command as a bridge-aware readiness
surface, not just a Git-managed component summary. When stage `gateway` is
active, it now exits non-zero if the local stage bridge request path is
degraded.

## Product-Specific Access

Use the shared component docs for shared services:

- Argo CD: [../components/argo-cd/README.md](../components/argo-cd/README.md)
- Vault: [../components/vault/README.md](../components/vault/README.md)
- Observability: [../components/observability/README.md](../components/observability/README.md)
- External Secrets: [../components/external-secrets/README.md](../components/external-secrets/README.md)
- Operator Orchestration Service: [../components/operator-orchestration-service/README.md](../components/operator-orchestration-service/README.md)
- Platform PostgreSQL: [../components/platform-postgresql/README.md](../components/platform-postgresql/README.md)
- Governed AI Gateway: [../components/governed-ai-gateway/README.md](../components/governed-ai-gateway/README.md)

Use the product-local runbooks for product details:

- OpenClaw: [../../products/openclaw/runbooks/access-openclaw.md](../../products/openclaw/runbooks/access-openclaw.md)
- OpenProject: [../../products/openproject/runbooks/access-openproject.md](../../products/openproject/runbooks/access-openproject.md)

OpenClaw also exposes a read-only Telegram operator surface for this shared
inventory through `/platform`. That command is driven by
[`platform-operator-catalog.yaml`](platform-operator-catalog.yaml) and should
stay aligned with this runbook.

## Notes

- Argo CD uses a self-signed certificate by default, so browsers will warn
  until you replace it.
- Vault is intentionally exposed over local HTTP because the current in-cluster
  chart is running with `tlsDisable: true`; keep it on localhost unless you add
  TLS.
- Host-side Ollama access for OpenClaw is refreshed by the managed Windows
  bootstrap path, not by these UI endpoints.
