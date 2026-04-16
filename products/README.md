# Products

This directory holds product-specific integration contracts that sit on top of
the shared platform.

Each product directory should explain how that product uses:

- the shared platform control plane
- the cluster and Argo model
- the secret-delivery model
- the host stack, if any
- the product’s own visibility and operating checks

## Why This Exists

The platform repo must scale beyond one product.

If product-specific runtime and release docs stay mixed into the shared platform
root forever, future products will always look like exceptions. This directory
is the place where product-specific integration material should accumulate.

## Required Product Files

At minimum, each product should have:

- `README.md`
- `runtime-contract.md`
- `dependencies.md`
- `visibility-and-operations.md`

Optional depending on the product:

- `host-integration.md`
- `secrets-and-config.md`
- product-specific workflow or runbook docs

## Current Products

- `openclaw/`
  - current AI runtime and host-control integration
- `openproject/`
  - internal supporting service integration
- `_template/`
  - starter structure for future products

Shared platform rules belong in [docs/standards](../docs/standards), not here.
