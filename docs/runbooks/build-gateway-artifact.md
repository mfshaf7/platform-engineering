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
5. build the bundled gateway image
6. push the image to GHCR using the pinned tag

## Current Runtime Split

- `stage` is still allowed to run `docker.io/library/openclaw:local` while the
  `Platform-Core` cutover soaks and while no governed published stage image has
  been promoted yet.
- the governed image build path already exists in
  [.github/workflows/build-gateway-image.yaml](../../.github/workflows/build-gateway-image.yaml)
  and now fails fast if the environment contract still contains placeholder
  source refs.
- `prod` should continue to use a published `ghcr.io/mfshaf7/openclaw-gateway`
  image, not an operator-local tag.

## Why This Matters

This preserves the current proven bundled-image build path while moving release
authority into the platform repo instead of leaving it as an operator-local
memory step.
