# OpenClaw Product Integration

This directory captures the platform-specific integration contract for OpenClaw.

It does not replace the canonical source repositories:

- `openclaw-telegram-enhanced`
- `openclaw-host-bridge`
- `openclaw-runtime-distribution`

Instead, it explains how OpenClaw uses the shared platform.

## What This Directory Covers

- OpenClaw runtime contract on the platform
- product dependencies
- host integration shape
- product visibility and operating checks

## What It Does Not Cover

- Telegram source implementation details
- host bridge implementation details
- security standards
- generic platform bootstrap

Those remain in their owning repos or in shared platform docs.

## Current Product Reality

OpenClaw is currently the deepest-integrated product in this platform.

That is why some incumbent runbooks and scripts at the repo root are still
OpenClaw-specific. Future products should use this product directory model more
directly instead of repeating that sprawl at the platform root.

## Start Here

- [runtime-contract.md](runtime-contract.md)
- [dependencies.md](dependencies.md)
- [host-integration.md](host-integration.md)
- [visibility-and-operations.md](visibility-and-operations.md)

For current incumbent OpenClaw release automation, also see:

- [../../scripts/README.md](../../scripts/README.md)
- [../../docs/runbooks/rebuild-and-promote-gateway.md](../../docs/runbooks/rebuild-and-promote-gateway.md)
- [../../docs/runbooks/promote-stage-to-prod.md](../../docs/runbooks/promote-stage-to-prod.md)
