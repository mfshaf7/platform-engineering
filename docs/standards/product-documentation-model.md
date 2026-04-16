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
- shared component architecture, access, and operations
- Vault and secret-delivery patterns
- host provisioning and shared host stack
- shared standards and governance
- shared decisions and change records
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
- product-specific operator scripts and helper modules under
  `products/<product>/scripts/`
- product-specific runbooks under `products/<product>/runbooks/`

## Script Classification

Top-level scripts should be one of:

1. shared platform
2. internal helper module
3. explicitly product-specific

If a script is product-specific, it should live under the owning product
directory instead of the shared `scripts/` tree.

Future direction:

- reusable platform scripts stay at `scripts/`
- product-specific operator entrypoints and helper modules live under
  `products/<product>/scripts/`

## Incumbent Product-Specific Material

Do not let “current reality” silently become “future standard.”

## Minimum Product Directory

Each product should have at least:

- `README.md`
- `runtime-contract.md`
- `dependencies.md`
- `visibility-and-operations.md`
- `AGENTS.md` when the product needs product-local operator guidance

Optional depending on the product:

- `host-integration.md`
- `secrets-and-config.md`
- product-specific runbooks or workflow docs
- `scripts/README.md`
- `runbooks/README.md`
