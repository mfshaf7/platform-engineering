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
- `runbooks/show-delivery-initiatives.md`
- `runbooks/show-delivery-active-front.md`
- `runbooks/check-delivery-art-quality.md`
- `runbooks/manage-proposal-to-delivery.md`
- `runbooks/start-delivery-execution.md`
- `runbooks/create-delivery-work-item.md`
- `runbooks/bulk-update-delivery-work-items.md`
- `runbooks/move-delivery-work-item.md`
- `runbooks/update-delivery-work-item.md`
- `runbooks/complete-delivery-work-item.md`
- `runbooks/manage-delivery-dependency.md`
- `runbooks/show-delivery-execution.md`
- `runbooks/show-delivery-planning.md`
- `runbooks/show-pi-objectives.md`
- `runbooks/record-pi-review.md`
- `runbooks/check-delivery-closeout-readiness.md`
- `runbooks/close-delivery-initiative.md`
- `runbooks/sync-delivery-art-views.md`
- `runbooks/update-delivery-initiative.md`
- `runbooks/record-system-demo.md`
- `runbooks/record-inspect-and-adapt.md`
- `runbooks/manage-delivery-blocker.md`
- `runbooks/manage-delivery-parking.md`
- `runbooks/prepare-production-clean-start.md`
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
  `product-governed` source-to-stage-to-prod workflow.
- Treat the current highest real endpoint as:
  - platform-managed runtime and operator flow on the local cluster
  - not a distinct product-governed stage rehearsal and prod-promotion model
- Operator access expectations, admin-password synchronization, and product
  lifecycle commands are OpenProject-specific and belong under this directory.
- Shared PostgreSQL behavior must still be evaluated as a platform dependency,
  not silently folded into OpenProject-only docs when the control is broader
  than the product.
- For serious delivery work already tracked in `Workspace Delivery ART`, start
  each session from the initiative summary and quality-check surfaces here
  instead of reconstructing the work queue from chat or handoff prose.

If an OpenProject task arrives:

- route it to the owning OpenProject product docs and scripts here
- complete it through the current platform-managed path
- do not claim a separate stage or prod promotion workflow unless that path is
  deliberately created later

## Delivery Work-State Rule

For work that is already inside `Workspace Delivery ART`:

- the ART is the primary work-state truth
- owner repos hold the implementation and design truth
- `workspace-governance` holds workspace-control truth

If a requested change is not already covered by the active ART:

- absorb it into the active work item only when it is a tiny same-slice patch
- otherwise add a new in-scope ART item when it belongs to the same initiative
- route it through `Workspace Proposals` when it is a new initiative
- route repeated process or control misses into `workspace-governance`
  improvement candidates
- route security or trust-boundary judgment into `security-architecture`

No meaningful delivery work should live only in chat.

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
  product-governed `source -> stage -> prod` promotion path
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
- `runbooks/manage-proposal-to-delivery.md`
- `runbooks/start-delivery-execution.md`
- `runbooks/show-delivery-initiatives.md`
- `runbooks/show-delivery-active-front.md`
- `runbooks/check-delivery-art-quality.md`
- `runbooks/create-delivery-work-item.md`
- `runbooks/bulk-update-delivery-work-items.md`
- `runbooks/move-delivery-work-item.md`
- `runbooks/update-delivery-work-item.md`
- `runbooks/complete-delivery-work-item.md`
- `runbooks/manage-delivery-dependency.md`
- `runbooks/show-delivery-execution.md`
- `runbooks/show-delivery-planning.md`
- `runbooks/show-pi-objectives.md`
- `runbooks/record-pi-review.md`
- `runbooks/check-delivery-closeout-readiness.md`
- `runbooks/close-delivery-initiative.md`
- `runbooks/sync-delivery-art-views.md`
- `runbooks/update-delivery-initiative.md`
- `runbooks/record-system-demo.md`
- `runbooks/record-inspect-and-adapt.md`
- `runbooks/manage-delivery-blocker.md`
- `runbooks/manage-delivery-parking.md`
- `runbooks/prepare-production-clean-start.md`
- `runbooks/configure-idea-backlog.md`
- `runbooks/configure-delivery-art.md`
- `runbooks/provision-operator-orchestration-identity.md`
