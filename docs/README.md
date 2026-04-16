# Platform Docs

This `docs/` tree is for shared platform material.

It should stay product-neutral.

## Shared Platform Docs

- `architecture/`
  - control planes, trust boundaries, platform-wide ADRs
- `standards/`
  - shared governance, release, secret, observability, and documentation rules
- `runbooks/`
  - shared platform operations and platform-level procedures

## Start Here For Real Operator Context

If you need to understand the current live platform rather than just the
governance model, start with:

- `architecture/current-platform-topology.md`
- `runbooks/access-platform-uis.md`

## Product-Specific Docs

Product-specific runtime and operating docs belong under:

- `products/openclaw/`
- `products/openproject/`
- `products/<future-product>/`

Use `products/_template/` when onboarding a new product.

## Product Rule

- shared platform procedures stay in `docs/`
- product-specific runtime contracts, scripts, runbooks, and visibility docs
  live under `products/<product>/`
