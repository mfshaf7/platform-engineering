# Product Boundaries

## Purpose

This standard defines what belongs to the shared platform and what belongs to an
individual product.

## Platform-Owned

These components must stay product-neutral so future products can reuse them
without renaming or cloning the platform layer:

- Argo root applications
- Argo projects
- cluster bootstrap and platform namespaces
- Vault and External Secrets integration patterns
- observability foundation
- CI/CD promotion contracts
- shared version metadata publication
- policy, security, and operator standards

## Product-Owned

These components should remain product-specific because they describe a product
runtime rather than the shared platform:

- product workloads and deployment charts
- product namespaces
- product images and build inputs
- product runtime secrets and Vault paths
- product-specific health, metrics, and host-integration behavior
- product source repositories and product runbooks

## Decision Rule

Use this test before naming or adding a new component:

- if another future product should reuse it unchanged, it belongs to the
  platform
- if another future product would need its own version, it belongs to the
  product

## Repository Pattern

- shared standards live under [docs/standards](../standards)
- shared control-plane assets live under the platform roots, charts, and
  environments
- product-specific integration contracts live under `products/<product>/`

## Current Product Contract Pattern

Each product directory should capture:

- purpose and ownership
- runtime contract
- dependencies
- host integration, if any
- secret path and deployment expectations

Use [products/_template/README.md](../../products/_template/README.md) as the
starting point for a new product.
