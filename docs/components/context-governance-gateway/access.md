# Context Governance Gateway Access

## Current State

CGG has no approved platform runtime access path.

- namespace: none approved
- Argo application: none
- direct browser UI: none
- API endpoint: none
- metadata store: none
- artifact store: none
- worker endpoint: none

The owner repo local CLI can be used for source-local context packet work, but
that is not a platform access path and not governed stage or prod evidence.

## Dev-Integration Access

The CGG dev-integration profile is build-admitted for owner-repo
implementation only. It is not self-serve launchable from the shared runner
until the workspace registry marks it `active` and the platform gate accepts
the implemented runtime shape.

Operators must not run or document a normal platform access path for:

```bash
make devint-up PROFILE=context-governance-gateway
make devint-access PROFILE=context-governance-gateway
```

until that profile is active and this file is updated with the exact namespace,
service, port-forward, smoke, and suspend or reset behavior.

## Future Governed Access Requirements

Before a governed stage or prod access path is added, the platform must define:

- service identity
- caller authentication
- authorization by operation
- network exposure model
- raw artifact access denial by default
- debug override approval and expiry behavior
- audit logging and receipt lookup behavior
- secret delivery and rotation path
- support and rollback owner

## Denied Access Patterns

Do not:

- describe local CLI use as platform runtime access
- expose raw artifacts through dashboard, API, logs, or port-forward by default
- bypass identity with a shared static production API key
- create a one-off `k3s` Service or Deployment outside the release gate
- point model-facing tools at raw CGG artifacts
