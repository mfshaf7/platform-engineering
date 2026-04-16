# platform-engineering

`platform-engineering` is the shared platform and release-governance repository
for the local multi-product stack.

OpenClaw is the most mature product currently integrated here, but it is only
one product. This repository should be understandable and reusable even when
more products are added later.

## What This Repository Owns

This repository owns shared platform concerns:

- environment contracts
- approved source SHAs and image digests
- Argo-managed deployment state
- host provisioning for the WSL and Windows platform stack
- shared architecture, standards, and runbooks
- product integration contracts under `products/<product>/`

It does not own product source implementations such as Telegram behavior, host
bridge code, or upstream application code.

## Platform Model

There are two layers in this repo:

1. shared platform layer
   - cluster bootstrap
   - Vault and secret-delivery patterns
   - Argo reconciliation
   - host provisioning
   - release governance
   - shared observability
2. product integration layer
   - runtime contract for each product
   - product dependencies
   - product visibility and operating checks
   - product-specific release and deployment notes

That split is implemented under:

- shared platform docs: `docs/`
- product integration docs: `products/<product>/`

## Current Product Set

- `products/openclaw/`
  - AI runtime and host-control product integration
- `products/openproject/`
  - internal project-management service integration
- `products/_template/`
  - template for future product onboarding

## Where To Start

### Shared platform

- [docs/README.md](docs/README.md)
- [docs/architecture/overview.md](docs/architecture/overview.md)
- [docs/standards/governed-change-model.md](docs/standards/governed-change-model.md)
- [docs/standards/product-boundaries.md](docs/standards/product-boundaries.md)
- [docs/standards/product-documentation-model.md](docs/standards/product-documentation-model.md)

### Product integrations

- [products/README.md](products/README.md)
- [products/openclaw/README.md](products/openclaw/README.md)
- [products/openproject/README.md](products/openproject/README.md)

## Operator Entrypoints

Top-level operator entrypoints exist in this repo, but they are not all
product-neutral.

- shared platform and provisioning commands:
  - `make provision-wsl-host`
  - `make provision-k3s-node`
  - `make verify-platform-host`
  - `make validate`
- OpenClaw-specific release commands:
  - `make gateway-pin`
  - `make gateway-validate`
  - `make gateway-record`
  - `make gateway-promote`
  - `make gateway-readiness`

See [scripts/README.md](scripts/README.md) for the current classification and
which scripts are shared vs OpenClaw-specific.

## Repository Layout

```text
platform-engineering/
|-- .github/workflows/
|-- ansible/
|-- argocd/
|-- charts/
|-- docs/
|-- environments/
|-- observability/
|-- products/
|-- scripts/
`-- terraform/
```
