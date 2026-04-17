# Platform Engineering Agent Notes

This repository is the shared platform and release-governance repo for multiple
products.

Do not let the platform root drift back into a product-specific dumping ground.

## Routing Rule

Start with:

- `README.md`
- `docs/components/README.md`
- `docs/decisions/adr/README.md`
- `docs/records/change-records/README.md`
- `docs/architecture/overview.md`
- `docs/architecture/current-platform-topology.md`
- `docs/workflows/README.md`
- `docs/runbooks/access-platform-uis.md`
- `docs/standards/README.md`
- `docs/standards/enterprise-workflow-model.md`
- `docs/standards/review-and-approval-model.md`
- `docs/standards/product-boundaries.md`
- `docs/standards/product-documentation-model.md`

Then route by scope:

- shared platform concern
  - stay in the repo root, `docs/`, `scripts/`, `ansible/`, `argocd/`,
    `charts/`, `environments/`, `observability/`, `terraform/`
- product-specific integration concern
  - go to `products/<product>/` and read that product's `AGENTS.md`

For shared components, route through `docs/components/<component>/README.md`
before editing scattered runbooks.

Current product-local agent guides:

- `products/openclaw/AGENTS.md`
- `products/openproject/AGENTS.md`

Shared path enforcement lives in `scripts/validate_repo_structure.py`.
The declarative structure contract lives in `repo-structure-manifest.yaml`.

Security review inputs and trust-boundary expectations are owned in
`security-architecture/`. Use that repo's review outputs and standards instead
of restating security governance locally.

Concrete security references for this repo:

- `security-architecture/docs/architecture/platform/trust-boundaries.md`
- `security-architecture/docs/architecture/domains/gitops-and-machine-trust.md`
- `security-architecture/docs/architecture/domains/secrets-and-recovery.md`
- `security-architecture/docs/standards/ai-security-and-governance.md`
- `security-architecture/docs/reviews/security-review-checklist.md`
- `security-architecture/docs/reviews/platform/2026-04-18-platform-engineering-security-baseline.md`
- `security-architecture/docs/reviews/platform/2026-04-18-governed-ai-intake-assist-and-model-profiles.md`

## Workflow Maturity Rule

Do not assume every product has the same delivery maturity as OpenClaw.

OpenClaw currently has the deepest end-to-end governed path. Other products may
only be platform-integrated or source-plus-ops integrated.

When a product-specific task lands here:

- read that product's `AGENTS.md` and `README.md`
- identify the highest real governed endpoint for that product
- stop there unless you are explicitly building the missing workflow

If a product does not yet have source-to-stage-to-prod flow, do not pretend it
does. Complete the work at the highest real owner layer and document the
missing rollout layer honestly.

## Architecture Discussion Gate

When a request would introduce a new product, shared component, ingress or
gateway layer, or another architecture-shaping platform capability, do not jump
straight into implementation.

Discuss with the user first:

- what problem the new capability is solving
- which control plane should own it
- whether it should be shared platform or product-specific
- what trust-boundary and operator-surface changes it creates
- what workflow maturity it should have on day one

Only start implementation after the target shape is explicit enough to route
cleanly.

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

## Documentation Sync Rule

When any of these change, update the shared docs in the same change:

- Argo application inventory
- namespace roles
- NodePort or Windows localhost access paths
- which platform surfaces are directly reachable
- whether a stage surface is live or intentionally suspended

The minimum shared docs to keep aligned are:

- `docs/components/README.md`
- `docs/decisions/adr/README.md`
- `docs/records/change-records/README.md`
- `docs/architecture/current-platform-topology.md`
- `docs/workflows/README.md`
- `docs/runbooks/access-platform-uis.md`

If the change is product-specific, also update the owning product docs and
runbooks under `products/<product>/`.

## Governance Artifact Rule

Use the shared workflow model:

- ADRs under `docs/decisions/adr/` for shared design and control decisions
- change records under `docs/records/change-records/` for production-impacting
  rollout evidence
- if a change altered both long-lived design and live governed state, both are
  required

For any meaningful PR, fill the governance declaration in:

- `.github/pull_request_template.md`

Do not use one as a substitute for the other.
