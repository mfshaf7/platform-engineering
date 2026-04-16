# Platform Engineering Agent Notes

This repository is the shared platform and release-governance repo for multiple
products.

Do not let the platform root drift back into a product-specific dumping ground.

## Routing Rule

Start with:

- `README.md`
- `docs/architecture/overview.md`
- `docs/standards/product-boundaries.md`
- `docs/standards/product-documentation-model.md`

Then route by scope:

- shared platform concern
  - stay in the repo root, `docs/`, `scripts/`, `ansible/`, `argocd/`,
    `charts/`, `environments/`, `observability/`, `terraform/`
- product-specific integration concern
  - go to `products/<product>/` and read that product's `AGENTS.md`

Current product-local agent guides:

- `products/openclaw/AGENTS.md`
- `products/openproject/AGENTS.md`

Shared path enforcement lives in `scripts/validate_repo_structure.py`.

## Shared Vs Product-Specific Placement

Keep these shared:

- platform bootstrap and provisioning
- Argo root apps and shared controller patterns
- Vault, secret-delivery, and shared observability patterns
- product-neutral standards and platform-wide runbooks
- shared platform scripts only

Keep these product-specific:

- product runtime and release runbooks
- product visibility and operations guidance
- product-specific scripts and helper modules
- product-specific lifecycle helpers

Shared docs stay in `docs/`.

Product docs, scripts, and runbooks stay in:

- `products/<product>/`
- `products/<product>/scripts/`
- `products/<product>/runbooks/`

## Non-Negotiable Rules

- Do not add new product-specific scripts at the repo-root `scripts/`.
- Do not add new product-specific runbooks under `docs/runbooks/`.
- Do not make the shared repo README or shared docs read like one product owns
  the platform.
- If a workflow, script, or runbook exists only for one product, move it to
  that product directory instead of marking it as another incumbent exception.
- Run or update `scripts/validate_repo_structure.py` when the shared-vs-product
  boundary changes.

## Operator Surface

Top-level `make` targets may still expose product-specific commands, but their
names must be product-qualified.

Examples:

- `make openclaw-gateway-pin`
- `make openclaw-gateway-promote`
- `make openproject-apply`

When you add or change a product-specific operator flow, update:

- the owning product `AGENTS.md`
- the owning product `README.md`
- the owning product `scripts/README.md` or `runbooks/README.md`

Do not expand this repo-root `AGENTS.md` with product-local incident lore when
that guidance belongs in a product directory.
