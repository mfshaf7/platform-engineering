# Operator Orchestration Service Operations

## Primary Checks

```bash
k3s kubectl -n argocd get application operator-orchestration-service
k3s kubectl -n operator-orchestration-service get deploy,svc,pod,externalsecret,secretstore
k3s kubectl -n operator-orchestration-service port-forward svc/operator-orchestration-service 8080:8080
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/readyz
curl -fsS http://127.0.0.1:8080/version
```

## Common Failure Signals

- broker pod runs but `/readyz` reports OpenProject config missing
- pod is healthy but OpenProject writes fail with authentication or validation errors
- stage `/idea` command fails while the service remains healthy
- External Secret is stale or missing in the component namespace
- stage readiness stays `pending` because the current candidate has no matching
  verification record
- prod verification stays `pending` because the shared deployment contract
  changed without a new post-promotion evidence record

## First Response

1. confirm the Argo application is synced and healthy
2. confirm the broker pod can read its secret material
3. check `/readyz` before debugging Telegram or OpenProject separately
4. if `/readyz` fails on OpenProject reachability, continue with OpenProject runtime checks

## Recovery Sequence

1. verify `operator-orchestration-service` Argo application health
2. verify `operator-orchestration-service-secrets` exists and is fresh
3. verify the broker deployment environment contains:
   - `OPENPROJECT_API_TOKEN`
   - `CALLER_AUTH_SHARED_SECRET`
4. verify `/readyz`
5. run one real stage `/idea` capture after repair

## Secret Provisioning Or Rotation

Caller secret material is broker-owned and should be written in Vault at:

- `kv/components/operator-orchestration-service/shared/runtime`
  - property: `callerSharedSecret`

Example operator path from WSL:

```bash
k3s kubectl -n vault exec vault-0 -- env \
  VAULT_ADDR=http://127.0.0.1:8200 \
  VAULT_TOKEN="$VAULT_TOKEN" \
  sh -lc 'vault kv put kv/components/operator-orchestration-service/shared/runtime callerSharedSecret="<new-secret>"'
```

OpenProject API token material remains at:

- `kv/components/operator-orchestration-service/prod/openproject`
  - property: `apiToken`

## Evidence To Capture

- Argo application state
- broker `/healthz`, `/readyz`, and `/version`
- OpenProject write error class if present
- one successful or failed stage `/idea` capture attempt

## Related Procedures

- [../../../products/openproject/idea-backlog-contract.md](../../../products/openproject/idea-backlog-contract.md)
- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
- [release-governance.md](release-governance.md)
