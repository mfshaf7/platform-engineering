# Vault Secret Rotation

## Purpose

This runbook defines how to rotate product runtime secrets in Vault without ad
hoc Kubernetes secret edits.

## Rule

Rotate secret data in Vault first. External Secrets Operator should propagate
the new material into Kubernetes.

## Example Path Pattern

- `products/openclaw/stage/gateway`
- `products/openclaw/prod/gateway`

## Write Updated Secret Data

```bash
export VAULT_TOKEN='...'
k3s kubectl -n vault exec vault-0 -- env VAULT_TOKEN="$VAULT_TOKEN" \
  vault kv put kv/products/openclaw/stage/gateway \
  OPENCLAW_GATEWAY_TOKEN='<new-token>'
```

Repeat for the target product and environment path.

## Force Immediate Refresh

```bash
k3s kubectl -n openclaw-stage annotate externalsecret openclaw-gateway-secrets force-sync="$(date +%s)" --overwrite
k3s kubectl -n openclaw annotate externalsecret openclaw-gateway-secrets force-sync="$(date +%s)" --overwrite
```

## Verify

- `k3s kubectl -n openclaw-stage get externalsecret openclaw-gateway-secrets`
- `k3s kubectl -n openclaw get externalsecret openclaw-gateway-secrets`
- runtime health endpoints remain healthy

## Do Not

- do not edit generated Kubernetes Secrets by hand as the primary rotation path
- do not commit plaintext secret values into Git
