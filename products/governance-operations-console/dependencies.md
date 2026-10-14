# Dependencies

## Source Repositories

- `governance-operations-console`: consumes the display-safe projection
- `operator-orchestration-service`: owns workflow authorization and canonical
  mutation
- `workspace-governance`: admits the `dev-integration` profile
- `security-architecture`: reviews the identity and authorization boundary
- `workspace-governance-control-fabric`: supplies canonical governance and
  readiness projections consumed by the Console

## Runtime Inputs

- an operator-owned `0600` dev-integration session manifest
- a policy-admitted active profile
- the matching local operating-system account
- `k3s kubectl` access to the exact runtime workloads admitted by
  `runtime-observation-policy.yaml`

The projection requires no token, browser secret, identity database, or new
network service.

Complete-runtime activation additionally requires current clean reviewed
owner revisions, the exact accepted Security `#1303` decision, `systemd --user`,
the existing `refinement-catalog`, and the local k3s `cni0` private gateway.
Its provider credential is generated at runtime and projected only from
Platform private state into the OOS namespace Secret.
