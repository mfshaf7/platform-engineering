# Workspace Governance Control Fabric Access

## Current State

WGCF now has a local dev-integration API access path.

- namespace: `devint-governance-control-fabric-<operator>`
- Argo application: none
- direct browser UI: none
- API endpoint: local k3s Service exposed by `make devint-access`
- metadata store: local k3s PostgreSQL StatefulSet and PVC
- evidence store: namespace-internal MinIO/S3-compatible Service and PVC
- worker endpoint: none

After the `governance-control-fabric` profile is active in the
`workspace-governance` registry on remote `main`, operators should use the
shared dev-integration runner. Until then, the owner authority gate rejects
these evidence-storage actions:

```bash
make devint-up PROFILE=governance-control-fabric
make devint-status PROFILE=governance-control-fabric
make devint-smoke PROFILE=governance-control-fabric
make devint-access PROFILE=governance-control-fabric
make devint-down PROFILE=governance-control-fabric
make devint-backup PROFILE=governance-control-fabric
make devint-restore PROFILE=governance-control-fabric \
  BACKUP_FILE=/path/to/wgcf-evidence-backup.tar.gz \
  CONFIRM=restore-wgcf-evidence
```

The object store has no direct operator UI or public endpoint. The WGCF API
Deployment is the only long-running workload that receives the bucket-scoped
application credential. Storage maintenance actions use an isolated temporary
pod and leave reference-only receipts in the operator profile state.

The local source repo commands remain valid for implementation checks:

```bash
cd "${WORKSPACE_ROOT}/workspace-governance-control-fabric"
.venv/bin/python scripts/validate_project.py --repo-root .
PYTHONPATH=packages/control_fabric_core/src:apps/api/src:apps/cli/src:apps/worker/src .venv/bin/python -m unittest discover -s tests
PYTHONPATH=packages/control_fabric_core/src:apps/api/src:apps/cli/src .venv/bin/python -m wgcf_cli status --repo-root .
```

Set `WORKSPACE_ROOT` to the local workspace root that contains the checked-out
`workspace-governance-control-fabric` repo.

## Future Governed Access Requirements

Before a governed stage or prod platform access path is added, the platform
must define:

- service identity and authentication model
- authorization for operator, CI, and automation callers
- network exposure model for local, stage, and prod
- audit logging and receipt lookup behavior
- validator invocation profile and allowed command classes
- secret delivery and rotation path
- support and rollback owner

## Denied Access Patterns

Do not:

- describe dev-integration access as approved stage or prod access
- document a Governance Operations Console URL before the console exists
- bypass platform identity with a shared static API key
- read raw artifacts through WGCF unless artifact custody and redaction policy
  are approved
- give OOS or OpenProject a storage credential or direct object URL
- run WGCF validator invocation as a replacement for direct validators before
  the platform gate and workspace shadow-parity gate both pass
