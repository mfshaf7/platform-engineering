# Context Governance Gateway Access

## Current State

CGG has a platform-accepted local `dev-integration` access path only after the
workspace registry marks the profile `active`.

- namespace: `devint-context-governance-gateway-<operator>` after activation
- Argo application: none
- direct browser UI: none
- API endpoint: local port-forward from the active dev-integration Service
- metadata store: local dev-integration PostgreSQL only
- artifact store: local dev-integration MinIO and PVC-backed CGG state only
- worker endpoint: no direct endpoint; worker runs in the dev-integration
  namespace

The owner repo local CLI can still be used for source-local context packet
work, but that is not a platform access path and not governed stage or prod
evidence.

## Dev-Integration Access

The CGG dev-integration profile is platform-accepted for active local-k3s
runtime operation. It is self-serve launchable only when the workspace registry
entry is `active`.

Use the shared runner from `platform-engineering/`:

```bash
make devint-up PROFILE=context-governance-gateway
make devint-access PROFILE=context-governance-gateway
make devint-smoke PROFILE=context-governance-gateway
make devint-down PROFILE=context-governance-gateway
```

`devint-access` holds a port-forward to:

- API health: `http://localhost:18280/healthz`
- dashboard summary: `http://localhost:18280/v1/operator/dashboard.txt`

The shared runner fails closed for launch, access, and smoke while the
workspace registry lifecycle is not `active`.

Suspend and reset behavior:

- `make devint-down PROFILE=context-governance-gateway` scales API, worker,
  PostgreSQL, and MinIO deployments to zero while preserving PVCs and local
  secrets.
- `make devint-reset PROFILE=context-governance-gateway` deletes the local
  namespace and local profile state. Treat this as destructive for local CGG
  artifacts, packets, receipts, and ledger state.

Shared smoke is read-only because the profile is persistent. It must not create
new work-tracking artifacts or project raw context into a model-safe packet.

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

## Dev-Integration Denied Patterns

Do not:

- use `dev-integration` access as governed `stage` or `prod` evidence
- bypass the workspace lifecycle gate by setting profile lifecycle variables
  during normal shared-runner operation
- expose raw artifacts through dashboard, API, logs, release records, or
  model-facing tools
- run mutating smoke against the persistent CGG lane

## Denied Access Patterns

Do not:

- describe local CLI use as platform runtime access
- expose raw artifacts through dashboard, API, logs, or port-forward by default
- bypass identity with a shared static production API key
- create a one-off `k3s` Service or Deployment outside the release gate
- point model-facing tools at raw CGG artifacts
