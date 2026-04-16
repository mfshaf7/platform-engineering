# Build Gateway Artifact

## Purpose

This runbook defines the intended gateway image build path under platform
governance.

## Source Of Truth

The platform repo drives the build through:

- [../../../environments/stage/versions.yaml](../../../environments/stage/versions.yaml)
- [../../../environments/prod/versions.yaml](../../../environments/prod/versions.yaml)
- [../../../.github/workflows/build-gateway-image.yaml](../../../.github/workflows/build-gateway-image.yaml)

The build uses pinned SHAs from:

- `openclaw-telegram-enhanced`
- `openclaw-host-bridge`
- `openclaw-runtime-distribution`

## Build Model

1. read the target environment version file
2. set or update the source pins from the actual local repo checkouts with
   `products/openclaw/scripts/gateway_release.py pin <env>`
   and clear any stale digest from the previous artifact candidate
3. check out the pinned source repos
4. stage Telegram and host-control packaged-runtime inputs from the standalone
   source repos into the runtime-distribution build workspace
5. run source-bundle validation and distribution verifiers
6. compute an immutable build tag from the pinned source bundle
7. build the bundled gateway image in GitHub Actions with Buildx
8. push the image and attestation metadata to GHCR
9. record the resulting digest in the environment that will deploy it only if the
   tag still matches the pinned source bundle

## Current Runtime Contract

- both `stage` and `prod` use governed GHCR-backed gateway images pinned by
  immutable digest
- the build path fails fast if the environment contract contains placeholder or
  invalid pinned refs
- the build workflow now reads the computed source-bundle metadata through
  `products/openclaw/scripts/gateway_release.py metadata` and validates the environment
  contract before build
- the bundled stage/prod image extends the official upstream base image pinned
  by digest in the environment contract
- `prod` must continue to use the published governed gateway image recorded by
  digest, never an operator-local tag
- deployment-owned runtime workspace templates are expected to come from
  `openclaw-runtime-distribution` and are validated before build
- for `stage`, the resulting digest is recorded into
  `environments/stage/release-candidate.yaml` before verification and approval
  are allowed
- for `prod`, any contract change must leave
  `environments/prod/verification.yaml` pending until post-promotion smoke or
  UAT is recorded

## Output Contract

The workflow publishes:

- a deterministic source-bundle tag in the form `<tagPrefix>-<sourceBundleRef>`
- OCI labels containing the pinned Telegram, host-bridge, runtime-distribution,
  and platform-engineering SHAs
- provenance and SBOM attestations through Buildx
- a build-time `platform-engineering` SHA that must be recorded back into the
  environment contract during digest promotion
- image identity that is environment-neutral for a given pinned source bundle;
  stage and prod may point at the same digest when promotion intentionally reuses
  the approved stage artifact

Promotion should prefer the immutable digest form:

- `<governed-gateway-image>@sha256:...`

Promotion completion should then record post-promotion prod smoke or UAT
against that exact digest and source bundle.

## Why This Matters

This preserves the current proven runtime-distribution build path while moving
release authority into the platform repo instead of leaving image creation as an
operator-local memory step.

## Prod Cutover Guardrails

- `Build Gateway Image` only creates the OCI artifact. It does not complete a prod rollout.
- After the build succeeds, warm the exact target digest on the prod node before committing the prod contract change.
- `python3 products/openclaw/scripts/gateway_release.py record prod ...` performs that external pre-pull automatically unless you pass `--skip-prepull`.
- `gateway_release.py record` refuses to write a digest when the supplied tag does
  not match the current deterministic source-bundle tag.
- `prod` gateway is a single-node `hostNetwork` workload that binds host port `18789`.
- Do not manually delete the old prod gateway pod as a first rollout step.
- Do not put a chart hook or Argo-managed pre-pull resource back on the sync path. The warm-up must happen before Argo sees the new digest.
