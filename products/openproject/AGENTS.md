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
- `scripts/README.md`
- `runbooks/README.md`

## Directory Contract

Keep OpenProject-specific platform material here:

- access, bootstrap, and uninstall runbooks
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
