# OpenClaw Product Integration Agent Notes

This directory owns the OpenClaw-specific platform integration model inside
`platform-engineering`.

It does not own the canonical OpenClaw source repositories. It owns how
OpenClaw is governed, packaged, promoted, and operated on this platform.

## Read First

- `README.md`
- `architecture-and-owner-model.md`
- `runtime-contract.md`
- `dependencies.md`
- `host-integration.md`
- `visibility-and-operations.md`
- `runbooks/access-openclaw.md`
- `scripts/README.md`
- `skills-src/README.md`
- `runbooks/README.md`

## Directory Contract

Keep OpenClaw-specific platform material here:

- architecture and owner-model docs
- release runbooks
- product-scoped operator scripts
- product-scoped Codex skills for governed OpenClaw delivery
- product visibility and operating checks
- product-local guidance about stage/prod behavior

Do not push new OpenClaw-specific operator guidance back into:

- `../../docs/runbooks/`
- `../../scripts/`
- `../../AGENTS.md`

unless it is genuinely shared platform behavior.

## OpenClaw Release Guardrails

- Treat `Build Gateway Image` as artifact creation only. A successful build does
  not mean prod is safe to swap yet.
- `prod` gateway is single-node and binds host port `18789`. Normal rolling
  updates can deadlock on port allocation.
- Prod cutover must use the external pre-pull sequence: warm the exact target
  digest on the node first, then commit the prod contract change, then let Argo
  reconcile.
- `python3 products/openclaw/scripts/gateway_release.py record prod ...` now
  performs that external pre-pull before it writes the prod digest by default.
- `stage` gateway rehearsals must use the same external pre-pull guardrail.
- Do not manually delete or restart the old prod gateway pod as a first resort.

## Stage Promotion Guardrails

- Keep `stage` suspended by default in source control.
- Resume only the components you are actively testing. Normal gateway rehearsal
  should use `gateway,version`, which activates `gateway + secrets + version`.
- Resume stage through
  `products/openclaw/scripts/set_stage_environment_state.py`, which owns the
  on-demand stage bridge lifecycle as well as the stage Argo kustomization.
- The stage bridge should not be left running while stage is suspended.
- Any stage lifecycle change resets promotion readiness.
- Candidate recording, verification, and approval are separate governed stages.
- `record stage` materializes `environments/stage/release-candidate.yaml`.
- Stage rehearsal must be written into `environments/stage/verification.yaml`
  before readiness approval is allowed.
- `promote stage prod` must reset `environments/prod/verification.yaml` to a
  pending or inactive state tied to the new prod contract and current prod
  lifecycle.
- A prod rollout is not operationally complete until post-promotion prod smoke
  or UAT is recorded in `environments/prod/verification.yaml`.
- Prod OpenClaw now has a governed lifecycle profile under
  `environments/prod/openclaw-lifecycle.yaml`.
- Change prod lifecycle only through
  `products/openclaw/scripts/set_prod_environment_state.py` or the matching
  GitHub workflow.
- The supported prod states are:
  - `live`
  - `traffic-stopped`
  - `suspended`
  - `quarantined`
- Suspending prod must only remove the OpenClaw prod slice. It must not prune
  OpenProject or unrelated shared prod services.
- `traffic-stopped` must cut product traffic at the deployment boundary, not by
  hiding product-specific traffic logic inside the Telegram repo.
- `traffic-stopped` may keep support surfaces such as version or secrets apps
  available if the lifecycle profile says so.
- `quarantined` must require an incident reference and block prod promotion.
- Returning prod to `live` requires fresh prod smoke/UAT before treating prod
  as operationally complete.
- `products/openclaw/platform-operator-catalog.yaml` is the platform-owned
  source of truth for the read-only Telegram `/platform` operator surface.
- the Telegram overlay artifact lane is allowed only as an explicit contract
  tied to a qualified OpenClaw base image.
- a Telegram overlay candidate may reach prod only when the same immutable
  overlay digest is stage-approved and the prod contract carries the same
  qualified base image.
- Prod promotion must fail closed unless
  `python3 products/openclaw/scripts/gateway_release.py readiness validate`
  passes against the current stage candidate.

## Workflow Dispatch Guardrails

- Trigger GitHub Actions only from the real WSL repo state, not a stale
  workspace copy.
- Extract GitHub dispatch tokens entirely inside WSL from the k3s secret path
  (`argocd/platform-engineering-repo`, data key `password`).
- Use `scripts/dispatch_github_workflow_from_k3s_secret.sh` for secret-backed
  workflow dispatch instead of ad hoc one-liners.

## Telegram Runtime Guardrails

- Treat Telegram customization as a packaged bundled-runtime seam, not a loose
  same-id plugin override.
- Shared stage/prod Telegram groups or topics are allowed only when they are
  intentional and risk-reviewed. In that model, startup backlog behavior must
  be explicit so a newly online bot does not replay buffered traffic meant for
  the other environment.
- A successful build is not enough after a base-image change. Re-run the
  compiled Telegram runtime smoke checks and validate real stage Telegram
  polling/reply before considering prod promotion.

## Documentation Sync Rule

When OpenClaw access or exposure changes, update these in the same change:

- `runtime-contract.md`
- `visibility-and-operations.md`
- `runbooks/access-openclaw.md`
- `runbooks/manage-prod-lifecycle.md`

If the change also affects shared operator entrypoints or stage/prod exposure,
update:

- `../../docs/architecture/current-platform-topology.md`
- `../../docs/runbooks/access-platform-uis.md`

## Governance Rule

When an OpenClaw platform change also changes shared platform design, use:

- `../../docs/decisions/adr/`

When an OpenClaw platform change materially changes governed stage, prod, or
host-owned live state, use:

- `../../docs/records/change-records/`

For meaningful PRs, fill the shared governance declaration in:

- `../../.github/pull_request_template.md`

## Review guidelines

For Codex GitHub review, treat the following as `P1` when they plausibly
regress the governed OpenClaw release path:

- any change that bypasses stage candidate recording, stage verification,
  readiness validation, prod lifecycle controls, or post-promotion prod
  verification
- Telegram overlay or gateway build changes that bypass qualified base-image
  matching or stage approval requirements
- lifecycle changes that avoid the documented product scripts or workflows and
  instead rely on ad hoc repo edits
- docs or contracts that describe OpenClaw rollout evidence as complete when
  the actual rehearsal, approval, or verification artifact is still missing
