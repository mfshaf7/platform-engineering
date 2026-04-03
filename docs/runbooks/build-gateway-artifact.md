# Build Gateway Artifact

## Purpose

This runbook defines the intended gateway image build path under platform
governance.

## Source Of Truth

The platform repo drives the build through:

- [environments/stage/versions.yaml](../../environments/stage/versions.yaml)
- [environments/prod/versions.yaml](../../environments/prod/versions.yaml)
- [.github/workflows/build-gateway-image.yaml](../../.github/workflows/build-gateway-image.yaml)

The build uses pinned SHAs from:

- `openclaw-telegram-enhanced`
- `openclaw-host-bridge`
- `openclaw-isolated-deployment`

## Build Model

1. read the target environment version file
2. check out the pinned source repos
3. sync the Telegram build copy into the deployment workspace
4. run workspace verification scripts
5. compute an immutable build tag from the pinned source bundle
6. build the bundled gateway image in GitHub Actions with Buildx
7. push the image and attestation metadata to GHCR
8. record the resulting digest in the environment that will deploy it

## Current Runtime Contract

- both `stage` and `prod` use governed GHCR-backed gateway images pinned by
  immutable digest
- the build path fails fast if the environment contract contains placeholder or
  invalid pinned refs
- the bundled stage/prod image extends the official upstream base image
  `ghcr.io/openclaw/openclaw:latest`
- `prod` must continue to use a published `ghcr.io/mfshaf7/openclaw-gateway`
  image recorded by digest, never an operator-local tag
- deployment-owned runtime workspace templates are expected to come from
  `openclaw-isolated-deployment` and are validated before build

## Output Contract

The workflow publishes:

- a deterministic environment tag in the form `<tagPrefix>-<sourceBundleRef>`
- OCI labels containing the pinned Telegram, host-bridge, isolated-deployment,
  and platform-engineering SHAs
- provenance and SBOM attestations through Buildx
- a build-time `platform-engineering` SHA that must be recorded back into the
  environment contract during digest promotion

Promotion should prefer the immutable digest form:

- `ghcr.io/mfshaf7/openclaw-gateway@sha256:...`

## Why This Matters

This preserves the current proven bundled-image build path while moving release
authority into the platform repo instead of leaving image creation as an
operator-local memory step.
