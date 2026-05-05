# Shared Platform Components

This directory is the operator-facing index for shared platform components.

Use it when the question is:

- where is this shared component documented
- how do I access it
- what namespace or Argo app owns it
- where is the architecture guidance
- where is the operations guidance

Product-specific runtimes do not belong here. Use `products/<product>/` for:

- OpenClaw
- OpenProject
- future product integrations

## Shared Component Documentation

Some documented components are live today. Others are admitted or planned
platform components whose docs intentionally say that no deployment is approved
yet. Use each component's `Current Live Footprint` section for live-state truth.

| Component | Overview | Architecture | Access | Operations |
| --- | --- | --- | --- | --- |
| Argo CD | [README.md](argo-cd/README.md) | [architecture.md](argo-cd/architecture.md) | [access.md](argo-cd/access.md) | [operations.md](argo-cd/operations.md) |
| Vault | [README.md](vault/README.md) | [architecture.md](vault/architecture.md) | [access.md](vault/access.md) | [operations.md](vault/operations.md) |
| Observability | [README.md](observability/README.md) | [architecture.md](observability/architecture.md) | [access.md](observability/access.md) | [operations.md](observability/operations.md) |
| External Secrets Operator | [README.md](external-secrets/README.md) | [architecture.md](external-secrets/architecture.md) | [access.md](external-secrets/access.md) | [operations.md](external-secrets/operations.md) |
| Platform PostgreSQL | [README.md](platform-postgresql/README.md) | [architecture.md](platform-postgresql/architecture.md) | [access.md](platform-postgresql/access.md) | [operations.md](platform-postgresql/operations.md) |
| Operator Orchestration Service | [README.md](operator-orchestration-service/README.md) | [architecture.md](operator-orchestration-service/architecture.md) | [access.md](operator-orchestration-service/access.md) | [operations.md](operator-orchestration-service/operations.md) |
| Workspace Governance Control Fabric | [README.md](workspace-governance-control-fabric/README.md) | [architecture.md](workspace-governance-control-fabric/architecture.md) | [access.md](workspace-governance-control-fabric/access.md) | [operations.md](workspace-governance-control-fabric/operations.md) |
| Context Governance Gateway | [README.md](context-governance-gateway/README.md) | [architecture.md](context-governance-gateway/architecture.md) | [access.md](context-governance-gateway/access.md) | [operations.md](context-governance-gateway/operations.md) |

Each shared component directory should keep the same file contract:

- `README.md`
- `architecture.md`
- `access.md`
- `operations.md`

Components that participate in governed release control should also publish:

- `release-governance.md`

Use [_template/](_template/README.md) when adding a new shared component doc
set.

## Read With

- [../architecture/current-platform-topology.md](../architecture/current-platform-topology.md)
- [../runbooks/access-platform-uis.md](../runbooks/access-platform-uis.md)
- [../../products/openclaw/README.md](../../products/openclaw/README.md)
- [../../products/openproject/README.md](../../products/openproject/README.md)

## Rule

When a shared platform component changes, update its component document here in
the same change.
