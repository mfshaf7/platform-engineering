# Build Telegram Overlay Image

## Purpose

Builds and pushes the stage-only OpenClaw Telegram overlay experiment image.

## Trigger

- manual `workflow_dispatch`

## Inputs Or Parameters

- none

The workflow always reads the current `stage` Telegram overlay experiment
contract from `products/openclaw/scripts/telegram_overlay_experiment.py
metadata`.

## Permissions And Approval Surface

- `contents: read`
- `packages: write`
- no separate GitHub environment gate; the workflow only builds the stage-only
  artifact and does not promote it

## Outputs And Side Effects

- packages the pinned standalone `openclaw-telegram-enhanced` source through
  the publishable packlist
- builds and pushes `ghcr.io/mfshaf7/openclaw-telegram-overlay:<tag>`
- emits the immutable digest that must be recorded back into the stage
  experiment contract before rehearsal

## Guardrails

- stage-only
- fails if the experiment is inactive
- verifies the pinned Telegram and runtime-distribution refs exist upstream
- smoke-checks that the overlay image contains the packaged Telegram runtime
  files and excludes test/declaration-only payloads

## Operator Evidence

- workflow run URL
- pushed overlay image digest
- pinned Telegram SHA
- subsequent `telegram_overlay_experiment.py record stage --digest ...`
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
  --digest sha256:<overlay-digest>
```
