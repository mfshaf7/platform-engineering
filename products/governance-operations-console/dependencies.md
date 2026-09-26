# Dependencies

## Source Repositories

- `governance-operations-console`: consumes the display-safe projection
- `operator-orchestration-service`: owns workflow authorization and canonical
  mutation
- `workspace-governance`: admits the `dev-integration` profile
- `security-architecture`: reviews the identity and authorization boundary

## Runtime Inputs

- an operator-owned `0600` dev-integration session manifest
- a policy-admitted active profile
- the matching local operating-system account

The projection requires no token, browser secret, identity database, or new
network service.
