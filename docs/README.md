# Platform Docs

This `docs/` tree is for shared platform material.

It should stay product-neutral.

## Truth Model

Shared platform docs use three different truth classes:

- target architecture
  - stable design intent and steady-state platform model
  - examples: `architecture/overview.md`, `standards/`, `decisions/`
- declared desired posture
  - Git-managed environment and lifecycle intent
  - examples outside this tree: `../environments/`, product lifecycle files
- observed live reality
  - current deployed topology and current operator access
  - examples: `architecture/current-platform-topology.md`,
    `runbooks/access-platform-uis.md`

Do not use the live-truth documents to define the intended architecture. Do not
use the target-architecture documents to claim what is running today.

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
  - includes the shared active-stack runtime drill and exact-baseline restore surface
  - `runbooks/legacy/`
    - retired or historical migration material that is intentionally separated
      from the current operator surface

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
