# OpenProject Product Integration Agent Notes

This directory owns the OpenProject-specific platform integration model inside
`platform-engineering`.

It does not own upstream OpenProject source code. It owns how OpenProject is
declared, operated, and verified on this platform.

## Read First

- `README.md`
- `runtime-contract.md`
- `dependencies.md`
- `secrets-and-config.md`
- `visibility-and-operations.md`
- `runbooks/access-openproject.md`
- `scripts/README.md`
- `runbooks/README.md`

## Directory Contract

Keep OpenProject-specific platform material here:

- access, bootstrap, and uninstall runbooks
- backup and restore runbooks
- product-scoped operator scripts
- OpenProject visibility and operator checks

Do not push new OpenProject-specific guidance back into:

- `../../docs/runbooks/`
- `../../scripts/`
- `../../AGENTS.md`

unless it is genuinely shared platform behavior.

## Current Operating Rules

- OpenProject is a supporting product or service on the platform, not the
  platform itself.
- Operator access expectations, admin-password synchronization, and product
  lifecycle commands are OpenProject-specific and belong under this directory.
- Shared PostgreSQL behavior must still be evaluated as a platform dependency,
  not silently folded into OpenProject-only docs when the control is broader
  than the product.

## Governance Rule

When an OpenProject change also changes shared platform design, use:

- `../../docs/decisions/adr/`

When an OpenProject change materially changes governed stage, prod, or
host-owned live state, use:

- `../../docs/records/change-records/`

For meaningful PRs, fill the shared governance declaration in:

- `../../.github/pull_request_template.md`

## Documentation Sync Rule

When OpenProject access, exposure, or admin credential flow changes, update:

- `runtime-contract.md`
- `visibility-and-operations.md`
- `runbooks/access-openproject.md`

When OpenProject backup, restore, or recovery workflow changes, also update:

- `runbooks/openproject-backup-restore.md`

If the change affects shared platform entrypoints, also update:

- `../../docs/architecture/current-platform-topology.md`
- `../../docs/runbooks/access-platform-uis.md`
