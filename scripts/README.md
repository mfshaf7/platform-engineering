# Shared Platform Scripts

This directory is now reserved for shared platform scripts only.

## Shared Platform Scripts

These support shared platform operations:

- `bootstrap_operator_access.sh`
- `bootstrap_vault.sh`
- `dispatch_github_workflow_from_k3s_secret.sh`
- `dev_integration.py`
  - runs the shared local-k3s `dev-integration` lane by dispatching a standard
    action such as `up`, `smoke`, or `promote-check` into a repo-owned profile
  - only launches profiles whose lifecycle is currently `active` in the
    workspace contract registry
- `dev_integration_auto_resume.py`
  - manages the optional profile-declared `operator-login` recovery policy
  - generates one secret-free user-systemd unit that replays the normal shared
    `up` path with the exact profile, operator, workspace, and source paths
  - removes the unit after a successful `down` or `reset`; profiles remain
    manual unless they explicitly opt in
- `dev_integration_compositions.py`
  - validates and executes workspace-registered runtime compositions through
    the existing single-profile runner
  - owns dependency ordering, reverse teardown, private runtime-generated
    credential custody, URL or host-port endpoint projection, declared caller
    and profile bindings, replay, and redacted composition state
- `dev_integration_host_services.py`
  - validates product-neutral persistent host-service declarations
  - supervises source-bound process identity, readiness, logs, status, and
    teardown without weakening cleanup for ordinary profile actions
- `platform_drill.py`
  - validates the shared machine-readable runtime-drill profile contract
  - scaffolds drill run state for baseline, verification, restore proof, and
    the operator-facing evidence pack copied into each run directory
  - reports drill status without pretending a temporary runtime exercise is the
    same thing as governed promotion
  - writes generated run state under `.platform-drills/`, which is local
    scratch state; promote durable outcomes through governed records instead of
    committing raw drill directories
- `repository_provider_identity.py`
  - validates and commissions the dedicated repository-custody GitHub App
    installation identity
  - mints a short-lived token limited to the exact requested repository set and
    `Metadata: read`, projects it to a Kubernetes Secret, and records only
    redacted identity evidence
  - revokes the issued provider token and removes the local projection without
    deleting or changing a repository
- `repository_provisioning_identity.py`
  - validates and commissions a separate organization-bound GitHub App for
    repository creation
  - delivers only a short-lived `Administration: write`, `Contents: read`, and
    implicit `Metadata: read` installation token to the active dev-integration
    session
  - records value-free evidence and revokes without compensating deletion
- `repository_lifecycle_identity.py`
  - validates and commissions a separate exact-repository GitHub App for
    archive and unarchive authority
  - delivers only a short-lived `Administration: write` and implicit
    `Metadata: read` token after immutable repository-id readback
  - records value-free evidence and revokes without altering repository state
- `workspace_intake_identity.py`
  - validates the stable Workspace Intake identity definition, verifies the
    exact GitHub App installation, and delivers or revokes one short-lived
    token for the admitted OOS dev-integration runtime
  - binds source revisions, caller, provider identity, runtime session, and
    rollback evidence in secret-free receipts
- `test_workspace_intake_identity.py`
  - checks exact scope and permissions, provider mismatch denials, runtime
    delivery and teardown, and secret-free receipt behavior using a local fake
    provider and runtime
- `test_repository_provider_identity.py`
  - proves positive commissioning and delivery plus unavailable, expired,
    over-privileged, mismatched, redirected, and revoked failure paths against a
    local fake provider
- `test_repository_provisioning_identity.py`
  - proves exact organization and permission binding, redacted delivery and
    revocation, and fail-closed mismatch, over-privilege, and redirect cases
- `test_repository_lifecycle_identity.py`
  - proves exact App, organization, repository, immutable id, and permission
    binding plus redacted delivery, revocation, and fail-closed scope cases

The default shared drill profile and evidence template live under:

- `../environments/shared/runtime-drills/active-stack-runtime-drill.yaml`
- `../environments/shared/runtime-drills/active-stack-runtime-drill-evidence-template.yaml`
- `migrate_k8s_secret_to_vault.py`
- `validate_ai_model_profiles.py`
- `test_ai_model_profiles.py`
- `test_governed_ai_gateway_policy.py`
- `test_governed_ai_gateway_runtime.py`
- `validate_environment_readiness.py`
- `validate_governance_docs.py`
- `validate_operational_docs.py`
- `validate_observability_taxonomy.py`
- `validate_repo_structure.py`
  - enforces the shared-vs-product repo boundary from
    `../repo-structure-manifest.yaml`
- `validate_single_host_scaling.py`
  - enforces the single-host default that new shared components and product
    runtimes stay at replica count `1` unless an explicit exemption is recorded
    in `../environments/shared/single-host-scaling-policy.yaml`

`validate_ai_model_profiles.py` checks the platform-owned governed AI model
profile registry, runtime-assist activation contract, access-plane source
contract, and devint egress policy under `../security/`, including cross-repo
references to `security-architecture` review artifacts and
`workspace-governance` output-schema contracts.

`test_governed_ai_gateway_policy.py` and
`test_governed_ai_gateway_runtime.py` prove exact caller, profile, task, schema,
and activation enforcement before provider access while preserving the intake
classifier compatibility response.

`validate_environment_readiness.py` evaluates the aggregate governed readiness
surface for `stage` or `prod` from the exact release-governance records under:

- `../environments/stage/environment-readiness.yaml`
- `../environments/prod/environment-readiness.yaml`

Use:

- `python3 scripts/validate_environment_readiness.py status stage`
- `python3 scripts/validate_environment_readiness.py validate stage`
- `python3 scripts/validate_environment_readiness.py status prod`
- `python3 scripts/validate_environment_readiness.py validate prod`

`validate_governance_docs.py` checks ADR and change-record structure, and the
shared PR governance template that routes future changes into the right
decision and evidence path. It also validates optional `security_evidence`
front matter on change records when a record is being used as structured
security remediation evidence.

`validate_operational_docs.py` checks workflow-doc coverage, freshness stamps
for current topology and access docs, the supported WSL host bootstrap
contract, the shared-vs-product operator-runbook boundary, and the
operator-surface split between current platform procedures and legacy migration
materials. It also checks that the shared component indexes in the repo root
and `docs/components/README.md` cover every governed shared component, and that
the OpenProject platform-admin contract in
`products/openproject/openproject-platform-admin-surface.json` still matches
the current product script inventory and doc markers.

`validate_observability_taxonomy.py` fail-closes the platform observability
baseline and overlay model so alerts, recording rules, dashboards, release
records, and product overlay catalogs cannot drift away from the agreed
platform-baseline / shared-component-overlay / product-overlay split without
being caught in validation.

`validate_single_host_scaling.py` checks the Git-managed platform runtime
surfaces under `environments/`, `products/`, and chart values files so new
components or products cannot quietly land with multi-replica runtime defaults
on the current single-host platform.

When you need to refresh the current platform topology doc against the live
local cluster, run:

- `python3 scripts/validate_operational_docs.py --repo-root . --check-live-cluster`

## Product-Specific Scripts

Product-specific entrypoints and helper modules must live under the owning
product directory:

- OpenClaw: [products/openclaw/scripts/README.md](../products/openclaw/scripts/README.md)
- OpenProject: [products/openproject/scripts/README.md](../products/openproject/scripts/README.md)

Do not add new product-specific scripts at the top level.
