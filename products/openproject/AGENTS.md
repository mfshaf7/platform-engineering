# OpenProject Product Integration Agent Notes

This directory owns the OpenProject-specific platform integration model inside
`platform-engineering`.

It does not own upstream OpenProject source code. It owns how OpenProject is
declared, operated, and verified on this platform.

## Read First

- `README.md`
- `runtime-contract.md`
- `idea-backlog-contract.md`
- `delivery-art-contract.md`
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
- idea backlog and delivery ART contracts
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
- OpenProject is currently a `platform-integrated` product, not a
  `fully governed` source-to-stage-to-prod workflow like OpenClaw.
- Treat the current highest real endpoint as:
  - platform-managed runtime and operator flow on the local cluster
  - not a distinct OpenClaw-style stage rehearsal and prod-promotion model
- Operator access expectations, admin-password synchronization, and product
  lifecycle commands are OpenProject-specific and belong under this directory.
- Shared PostgreSQL behavior must still be evaluated as a platform dependency,
  not silently folded into OpenProject-only docs when the control is broader
  than the product.

If an OpenProject task arrives:

- route it to the owning OpenProject product docs and scripts here
- complete it through the current platform-managed path
- do not claim a separate stage or prod promotion workflow unless that path is
  deliberately created later

When the change affects the canonical project model used by operator workflows
or automation, keep the contract in:

- `idea-backlog-contract.md`
- `delivery-art-contract.md`

## Governance Rule

When an OpenProject change also changes shared platform design, use:

- `../../docs/decisions/adr/`

When an OpenProject change materially changes governed stage, prod, or
host-owned live state, use:

- `../../docs/records/change-records/`

For meaningful PRs, fill the shared governance declaration in:

- `../../.github/pull_request_template.md`

## Review guidelines

For Codex GitHub review, treat the following as `P1` when they plausibly
misstate the OpenProject operating model:

- wording or workflow changes that imply OpenProject already has an
  OpenClaw-style governed `source -> stage -> prod` promotion path
- wording or workflow changes that stop describing OpenProject as
  `platform-integrated` and instead imply a deeper governed rollout maturity
- changes to backlog, access, backup, restore, or credential flow that do not
  update the owning product docs and runbooks
- shared dependency or platform-surface changes that are hidden only in
  product-local docs instead of being routed back to shared platform guidance

## Documentation Sync Rule

When OpenProject access, exposure, or admin credential flow changes, update:

- `runtime-contract.md`
- `idea-backlog-contract.md`
- `visibility-and-operations.md`
- `runbooks/access-openproject.md`

When OpenProject backup, restore, or recovery workflow changes, also update:

- `runbooks/openproject-backup-restore.md`

If the change affects shared platform entrypoints, also update:

- `../../docs/architecture/current-platform-topology.md`
- `../../docs/runbooks/access-platform-uis.md`

When the change affects the canonical proposal-to-delivery project model or the
broker's OpenProject access path, also update:

- `idea-backlog-contract.md`
- `delivery-art-contract.md`
- `runbooks/configure-idea-backlog.md`
- `runbooks/configure-delivery-art.md`
- `runbooks/provision-operator-orchestration-identity.md`
