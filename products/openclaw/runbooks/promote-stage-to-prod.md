# Promote Stage To Prod

## Purpose

This runbook defines the intended promotion path between the two declared
environments.

## Expected Flow

1. update and validate `stage`
2. build and publish the gateway artifact for the approved stage source bundle
3. record the stage candidate into `environments/stage/release-candidate.yaml`
4. allow Argo CD to reconcile `stage`
5. rehearse the current candidate on `stage` and record structured evidence in
   `environments/stage/verification.yaml`
6. run `.github/workflows/confirm-stage-promotion-readiness.yaml` to approve
   the exact verified candidate
7. run `.github/workflows/promote-environment.yaml`
8. approve the protected `prod` promotion job and review the generated PR
9. merge the production promotion change
10. rehearse `prod` against the promoted candidate and record
    `environments/prod/verification.yaml`
11. treat the rollout as complete only after the prod smoke or UAT evidence is
    recorded

## Current Promotion Contract

- `stage` now runs a governed GHCR-backed gateway image pinned by digest.
- promotion to `prod` is allowed only from `stage` to `prod`.
- the promotion workflow copies the approved digest and source SHAs into the
  `prod` contract and opens a PR instead of mutating `main` directly.
- promotion approval must match both
  `environments/stage/release-candidate.yaml` and
  `environments/stage/verification.yaml`; changing either invalidates
  readiness until the next approval is recorded.
- the promotion workflow must reset `environments/prod/verification.yaml` to a
  pending or inactive state bound to the newly promoted prod contract and
  current prod lifecycle.
- the promoted artifact is source-bundle based, not stage-branded; prod should
  reuse the approved stage digest instead of rebuilding a separate prod-only
  image for the same pinned source bundle.
- the workflow should be bound to a protected GitHub environment named `prod`
  so required reviewers gate the job before the PR is created.

## Immutable Promotion Rule

- record the produced GHCR digest in the target environment values before
  rollout
- prefer `repository@sha256:...` over mutable tag-only deployment references
- keep the image tag for operator readability, but treat the digest as the
  deployment truth

## Current Operator Inputs

- [../../../environments/stage/versions.yaml](../../../environments/stage/versions.yaml)
- [../../../environments/prod/versions.yaml](../../../environments/prod/versions.yaml)
- [../../../.github/workflows/promote-environment.yaml](../../../.github/workflows/promote-environment.yaml)
- [../scripts/gateway_release.py](../scripts/gateway_release.py)

## Stage Behavior Gate

Do not treat stage as promotion-ready from health endpoints alone. When the
candidate changes Telegram, host-control, or the OpenClaw base image, stage must
prove the real operator paths:

- normal Telegram reply
- Telegram file send from the shared media path
- Telegram screenshot delivery
- deterministic host-control topic routing
- any admin/high-risk host-control path only when it is deliberately enabled in
  the stage contract
- if stage and prod intentionally share Telegram groups or topics, the startup
  backlog policy must be explicit so the promoted bot does not replay buffered
  traffic when it comes online

The current default promotion checks are recorded through
`products/openclaw/verification-catalog.yaml`:

- `runtime-start`
- `primary-user-path`
- `artifact-delivery`
- `screenshot-delivery`
- `privileged-path-posture`

These are policy-driven checks, not a permanently fixed schema. Candidate
requirements may evolve as OpenClaw gains new capabilities.

## Post-Promotion Prod Smoke Or UAT

Prod promotion does not redo the full stage rehearsal pack by default. Instead,
it records a narrow smoke or UAT evidence set in
`environments/prod/verification.yaml` against the exact promoted prod contract.

The current baseline checks come from
`products/openclaw/prod-verification-catalog.yaml`:

- `reconciliation-state`
- `primary-user-path-smoke`
- `operator-surface-smoke`

This is the expected evidence pattern for a user-facing Telegram product:

- one proof that Argo and the live deployment really reconciled the approved
  digest
- one real inbound prod interaction
- one read-only prod operator interaction such as `/platform`

See [verify-prod-after-promotion.md](verify-prod-after-promotion.md).

If prod OpenClaw is deliberately suspended, promotion may still update the prod
contract while leaving the runtime offline. In that case prod verification
stays inactive until the governed prod lifecycle returns to `live`.

## Stage Bridge Lifecycle

Stage host control now assumes an on-demand bridge instance instead of a shared
always-on listener.

- resume stage through
  `products/openclaw/scripts/set_stage_environment_state.py`, not by editing
  the stage Argo kustomization by hand
- the resume path must start `openclaw-host-bridge-stage.service` and confirm
  its health before the stage gateway is allowed back online
- the suspend path should stop `openclaw-host-bridge-stage.service` after the
  stage gateway is removed
- prod steady state should keep only the prod bridge listener online
