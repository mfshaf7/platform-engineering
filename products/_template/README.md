# Product Integration Template

Copy this directory when onboarding a new product onto the platform.

The product directory should define the product’s integration contract with the
shared platform without duplicating the upstream source repository.

## Minimum Files

- `README.md`
- `runtime-contract.md`
- `dependencies.md`
- `visibility-and-operations.md`
- `AGENTS.md` when the product needs product-local operator guidance

Add these when relevant:

- `host-integration.md`
- `secrets-and-config.md`
- `runbooks/access-<product>.md` when the product has a direct operator or
  user-facing access path
- product-specific workflow or runbook docs
- `scripts/README.md`
- `runbooks/README.md`

## Product README Expectations

The product README should answer:

- what the product is
- what this repo owns for the product
- what upstream repo or chart remains canonical
- current workflow maturity:
  - source-only
  - platform-integrated
  - fully governed
- whether stage exists for the product
- whether governed prod promotion exists for the product
- the highest implemented operator endpoint today
- where to find runtime, dependency, and visibility docs
- where to find direct access and login guidance, if the product exposes any
- which operator flow is shared platform vs product-specific
- where product-local scripts and runbooks live

## Governance Expectation

Product-local work still uses shared governance artifacts when required:

- ADR in `../../docs/decisions/adr/` when shared platform design changed
- change record in `../../docs/records/change-records/` when governed live
  state changed
- PR declaration in `../../.github/pull_request_template.md` for meaningful
  changes

For a fully governed product with a rehearsal lane, prefer explicit release
state objects over helper-script memory alone:

- `release-candidate.yaml`
- `verification.yaml`
- `promotion-readiness.yaml`
