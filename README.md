# platform-engineering

`platform-engineering` is the shared platform and release-governance repository
for the local multi-product stack.

OpenClaw is the most mature product currently integrated here, but it is only
one product. This repository should be understandable and reusable even when
more products are added later.

Security standards, trust-boundary review, and durable security evidence are
owned in `security-architecture/`, not duplicated here.

Concrete security review references for this repo:

- [`security-architecture/docs/architecture/platform/trust-boundaries.md`](https://github.com/mfshaf7/security-architecture/blob/main/docs/architecture/platform/trust-boundaries.md)
- [`security-architecture/docs/architecture/domains/gitops-and-machine-trust.md`](https://github.com/mfshaf7/security-architecture/blob/main/docs/architecture/domains/gitops-and-machine-trust.md)
- [`security-architecture/docs/architecture/domains/secrets-and-recovery.md`](https://github.com/mfshaf7/security-architecture/blob/main/docs/architecture/domains/secrets-and-recovery.md)
- [`security-architecture/docs/reviews/security-review-checklist.md`](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/security-review-checklist.md)
- [`security-architecture/docs/reviews/platform/README.md`](https://github.com/mfshaf7/security-architecture/blob/main/docs/reviews/platform/README.md)

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
- [docs/components/README.md](docs/components/README.md)
- [docs/decisions/adr/README.md](docs/decisions/adr/README.md)
- [docs/records/change-records/README.md](docs/records/change-records/README.md)
- [docs/architecture/overview.md](docs/architecture/overview.md)
- [docs/architecture/current-platform-topology.md](docs/architecture/current-platform-topology.md)
- [docs/workflows/README.md](docs/workflows/README.md)
- [docs/runbooks/access-platform-uis.md](docs/runbooks/access-platform-uis.md)
- [docs/standards/README.md](docs/standards/README.md)
- [docs/standards/enterprise-workflow-model.md](docs/standards/enterprise-workflow-model.md)
- [docs/standards/review-and-approval-model.md](docs/standards/review-and-approval-model.md)
- [docs/standards/governed-change-model.md](docs/standards/governed-change-model.md)
- [docs/standards/product-boundaries.md](docs/standards/product-boundaries.md)
- [docs/standards/product-documentation-model.md](docs/standards/product-documentation-model.md)

### Product integrations

- [products/README.md](products/README.md)
- [products/openclaw/README.md](products/openclaw/README.md)
- [products/openproject/README.md](products/openproject/README.md)
- [products/openclaw/runbooks/access-openclaw.md](products/openclaw/runbooks/access-openclaw.md)
- [products/openproject/runbooks/access-openproject.md](products/openproject/runbooks/access-openproject.md)

## If You Need To Know What Exists Right Now

Start here in this order:

1. [docs/architecture/current-platform-topology.md](docs/architecture/current-platform-topology.md)
2. [docs/runbooks/access-platform-uis.md](docs/runbooks/access-platform-uis.md)
3. the relevant product access runbook under `products/<product>/runbooks/`

Those documents are meant to answer:

- what is deployed
- where it lives
- what is directly reachable
- how to log in
- what is intentionally internal-only or suspended

For enterprise workflow governance, also use:

- [docs/workflows/README.md](docs/workflows/README.md)
- [docs/standards/README.md](docs/standards/README.md)
- [docs/standards/enterprise-workflow-model.md](docs/standards/enterprise-workflow-model.md)
- [docs/standards/review-and-approval-model.md](docs/standards/review-and-approval-model.md)
- [.github/pull_request_template.md](.github/pull_request_template.md)

## Shared Component Map

For shared component architecture and operations, use:

- [docs/components/argo-cd/README.md](docs/components/argo-cd/README.md)
- [docs/components/vault/README.md](docs/components/vault/README.md)
- [docs/components/observability/README.md](docs/components/observability/README.md)
- [docs/components/external-secrets/README.md](docs/components/external-secrets/README.md)
- [docs/components/platform-postgresql/README.md](docs/components/platform-postgresql/README.md)

## Operator Entrypoints

Top-level operator entrypoints exist in this repo, but they are not all
product-neutral.

- shared platform and provisioning commands:
  - `make provision-wsl-host`
  - `make provision-k3s-node`
  - `make verify-platform-host`
  - `make validate`
- OpenClaw-specific release commands:
  - `make openclaw-gateway-pin`
  - `make openclaw-gateway-validate`
  - `make openclaw-gateway-record`
  - `make openclaw-gateway-promote`
  - `make openclaw-gateway-readiness`
- OpenProject-specific commands:
  - `make openproject-apply`
  - `make openproject-status`
  - `make openproject-access`
  - `make openproject-uninstall`

See [scripts/README.md](scripts/README.md) for shared platform scripts, then use
the product-local script indexes:

- [products/openclaw/scripts/README.md](products/openclaw/scripts/README.md)
- [products/openproject/scripts/README.md](products/openproject/scripts/README.md)

`make validate` now includes the shared structure guard
`scripts/validate_repo_structure.py` so product-specific files cannot drift back
into shared `docs/runbooks/` or `scripts/` unnoticed. It also validates the
governance documentation, workflow docs, and review surface.

The shared-vs-product structure contract for this repo lives in
[repo-structure-manifest.yaml](repo-structure-manifest.yaml), not only inside
the validator code.

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
