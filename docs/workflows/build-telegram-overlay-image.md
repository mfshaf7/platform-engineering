# Build Telegram Overlay Image

## Purpose

Builds and pushes the OpenClaw Telegram overlay image for the current qualified
stage lane.

## Trigger

- manual `workflow_dispatch`

## Inputs Or Parameters

- none

The workflow always reads the current `stage` Telegram overlay
contract from `products/openclaw/scripts/telegram_overlay_experiment.py
metadata`.

## Permissions And Approval Surface

- `contents: read`
- `packages: write`
- no separate GitHub environment gate; the workflow only builds the overlay
  artifact and does not promote it directly

## Outputs And Side Effects

- packages the pinned standalone `openclaw-telegram-enhanced` source through
  the publishable packlist
- builds and pushes `ghcr.io/mfshaf7/openclaw-telegram-overlay:<tag>`
- emits the immutable digest that must be recorded back into the stage
  contract before rehearsal or governed promotion

## Guardrails

- fails if the overlay lane is inactive
- verifies the pinned Telegram and runtime-distribution refs exist upstream
- verifies the lane carries a qualified OpenClaw base image
- smoke-checks that the overlay image contains the packaged Telegram runtime
  files and excludes test/declaration-only payloads

## Operator Evidence

- workflow run URL
- pushed overlay image digest
- pushed overlay image tag
- pinned Telegram SHA
- qualified OpenClaw base image
- subsequent `telegram_overlay_experiment.py record stage --digest ... --tag ...`
  evidence once the digest is written into the stage contract

## Related Docs

- [../../products/openclaw/runbooks/stage-telegram-overlay-experiment.md](../../products/openclaw/runbooks/stage-telegram-overlay-experiment.md)
- [../../products/openclaw/runtime-contract.md](../../products/openclaw/runtime-contract.md)
- [../../products/openclaw/architecture-and-owner-model.md](../../products/openclaw/architecture-and-owner-model.md)
- [../build-gateway-image.md](build-gateway-image.md)

## Follow-up

Recording the digest is a separate governed step:

```bash
python3 products/openclaw/scripts/telegram_overlay_experiment.py record stage \
  --digest sha256:<overlay-digest> \
  --tag telegram-overlay-<pinned-telegram-sha-prefix>
```
