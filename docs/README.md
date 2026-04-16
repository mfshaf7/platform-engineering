# Platform Docs

This `docs/` tree is for shared platform material.

It should stay product-neutral unless a file is explicitly marked as legacy
product-specific material that has not yet been migrated into `products/`.

## Shared Platform Docs

- `architecture/`
  - control planes, trust boundaries, platform-wide ADRs
- `standards/`
  - shared governance, release, secret, observability, and documentation rules
- `runbooks/`
  - shared platform operations and platform-level procedures

## Product-Specific Docs

Product-specific runtime and operating docs belong under:

- `products/openclaw/`
- `products/openproject/`
- `products/<future-product>/`

Use `products/_template/` when onboarding a new product.

## Current Migration Reality

This repo still contains some incumbent OpenClaw-focused runbooks at the shared
docs layer because OpenClaw was the first deeply integrated product.

Going forward:

- shared platform procedures stay in `docs/`
- product-specific runtime contracts, visibility docs, and future product
  runbooks should live under `products/<product>/`
