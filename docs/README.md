# Platform Docs

This `docs/` tree is for shared platform material.

It should stay product-neutral.

## Shared Platform Docs

- `architecture/`
  - control planes, trust boundaries, current topology, and platform-wide
    architecture views
- `components/`
  - shared platform components with direct links to architecture, access, and
    operations guidance
- `workflows/`
  - operator-facing documentation for GitHub workflow entrypoints and approval
    surfaces
- `standards/`
  - shared governance, release, secret, observability, and documentation rules
- `decisions/`
  - ADRs and design rationale for shared platform changes
- `records/`
  - change records and governed rollout evidence
- `runbooks/`
  - shared platform operations and platform-level procedures

## Start Here For Real Operator Context

If you need to understand the current live platform rather than just the
governance model, start with:

- `decisions/adr/README.md`
- `records/change-records/README.md`
- `components/README.md`
- `architecture/current-platform-topology.md`
- `workflows/README.md`
- `runbooks/access-platform-uis.md`
- `standards/README.md`

For meaningful PRs, also use the governance declaration in:

- `../.github/pull_request_template.md`

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
