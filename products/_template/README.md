# Product Integration Template

Copy this directory when onboarding a new product onto the platform.

The product directory should define the product’s integration contract with the
shared platform without duplicating the upstream source repository.

## Minimum Files

- `README.md`
- `runtime-contract.md`
- `dependencies.md`
- `visibility-and-operations.md`

Add these when relevant:

- `host-integration.md`
- `secrets-and-config.md`
- product-specific workflow or runbook docs

## Product README Expectations

The product README should answer:

- what the product is
- what this repo owns for the product
- what upstream repo or chart remains canonical
- where to find runtime, dependency, and visibility docs
- which operator flow is shared platform vs product-specific
