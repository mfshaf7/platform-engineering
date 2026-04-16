# Build Gateway Image

## Purpose

This workflow builds and pushes the governed OpenClaw gateway image from pinned
source refs.

It is artifact creation only. It does not record the digest into an environment
contract and does not deploy anything by itself.

## Trigger

- manual `workflow_dispatch`

## Inputs Or Parameters

- `environment`
  - `stage` or `prod`

## Permissions And Approval Surface

- repository read
- package write to GHCR
- uses cross-repo read token for pinned source verification
- no environment gate because it does not change governed runtime state

## Outputs And Side Effects

- pushed image tag in GHCR
- image digest in workflow logs and outputs
- smoke-test evidence for the bundled Telegram and host-control runtime path

## Operator Evidence

Capture:

- workflow run URL
- published image tag
- published digest
- pinned Telegram, host-bridge, runtime-distribution, and platform refs

## Related Docs

- [../../products/openclaw/runbooks/build-gateway-artifact.md](../../products/openclaw/runbooks/build-gateway-artifact.md)
- [../standards/artifact-build.md](../standards/artifact-build.md)
