# Operator Orchestration Service Access

There is no shared browser UI for `operator-orchestration-service`.

The Governance Operations Console calls OOS only. It does not receive a direct
CGG endpoint or lifecycle caller credential. Platform operators activate and
inspect that local binding through the
[Lifecycle Context Composition](../../../dev-integration/compositions/lifecycle-context/README.md).

## WSL Fallback

```bash
k3s kubectl -n operator-orchestration-service port-forward svc/operator-orchestration-service 8080:8080
```

Then use:

- `http://127.0.0.1:8080/healthz`
- `http://127.0.0.1:8080/readyz`
- `http://127.0.0.1:8080/version`

## Credentials

- OpenProject token source:
  - Vault path `kv/components/operator-orchestration-service/prod/openproject`
- caller-auth shared secret source:
  - Vault path `kv/components/operator-orchestration-service/shared/runtime`
- repository-provider GitHub App private-key source:
  - Vault path
    `kv/components/operator-orchestration-service/dev-integration/repository-provider`
  - property `privateKey`
- repository-provisioning GitHub App private-key source:
  - Vault path
    `kv/components/operator-orchestration-service/dev-integration/repository-provisioning-provider`
  - property `privateKey`
- Agent source GitHub App private-key source:
  - Vault path
    `kv/components/operator-orchestration-service/dev-integration/agent-source`
  - property `privateKey`

Agent source tokens are projected only beneath the current operator's
`XDG_RUNTIME_DIR` using the path declared in
[agent-source-identity.yaml](../../../security/agent-source-identity.yaml).
They are not mounted into the browser or stored in OOS work-session state.

Do not surface any of these credentials in Console responses, product config,
Git-tracked docs, logs, receipts, or command arguments.

The lifecycle-context caller secret is generated at activation, projected only
to the operator-scoped OOS and CGG deployments, and removed by suspension,
teardown, or rollback. Durable state and receipts contain its digest only.
