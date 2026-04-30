# Workspace Governance Control Fabric Access

## Current State

There is no live platform access path for WGCF.

- namespace: none
- Argo application: none
- direct browser UI: none
- API endpoint: none
- worker endpoint: none

Operators should use the local source repo commands while WGCF remains in
bootstrap posture:

```bash
cd "${WORKSPACE_ROOT}/workspace-governance-control-fabric"
.venv/bin/python scripts/validate_project.py --repo-root .
PYTHONPATH=packages/control_fabric_core/src:apps/api/src:apps/cli/src:apps/worker/src .venv/bin/python -m unittest discover -s tests
PYTHONPATH=packages/control_fabric_core/src:apps/api/src:apps/cli/src .venv/bin/python -m wgcf_cli status --repo-root .
```

Set `WORKSPACE_ROOT` to the local workspace root that contains the checked-out
`workspace-governance-control-fabric` repo.

## Future Access Requirements

Before a platform access path is added, the platform must define:

- service identity and authentication model
- authorization for operator, CI, and automation callers
- network exposure model for local, stage, and prod
- audit logging and receipt lookup behavior
- secret delivery and rotation path
- support and rollback owner

## Denied Access Patterns

Do not:

- expose the API with ad hoc port-forwards as approved operator access
- document a Governance Operations Console URL before the console exists
- bypass platform identity with a shared static API key
- read raw artifacts through WGCF unless artifact custody and redaction policy
  are approved
