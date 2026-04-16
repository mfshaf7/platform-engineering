# Product Documentation Model

## Purpose

This standard defines how documentation should be split between the shared
platform and individual product integrations.

It exists because the platform must scale to multiple products without making
the shared repo read like it belongs to only one of them.

## Core Rule

Shared platform docs explain reusable control planes.

Product docs explain how one product uses those control planes.

## Shared Platform Docs

Keep these in `docs/`:

- cluster and Argo architecture
- Vault and secret-delivery patterns
- host provisioning and shared host stack
- shared standards and governance
- product-neutral operator workflows
- platform-wide incident and rollback procedures

## Product Docs

Keep these in `products/<product>/`:

- product purpose and ownership
- runtime contract
- dependencies
- secrets and config expectations
- host integration, if any
- visibility and operations guidance
- product-specific release or verification workflow

## Script Classification

Top-level scripts should be one of:

1. shared platform
2. internal helper module
3. explicitly product-specific

If a script is product-specific, the docs should say so explicitly.

Future direction:

- reusable platform scripts stay at `scripts/`
- product-specific operator entrypoints should either be clearly prefixed or
  documented from the matching `products/<product>/` directory

## Incumbent Product-Specific Material

When the shared platform already contains product-specific material from the
first integrated product, mark it as incumbent and avoid repeating that pattern
for future products.

Do not let “current reality” silently become “future standard.”

## Minimum Product Directory

Each product should have at least:

- `README.md`
- `runtime-contract.md`
- `dependencies.md`
- `visibility-and-operations.md`

Optional depending on the product:

- `host-integration.md`
- `secrets-and-config.md`
- product-specific runbooks or workflow docs
