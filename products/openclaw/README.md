# OpenClaw Product Integration

This directory captures the platform-specific integration contract for OpenClaw.

It does not replace the canonical source repositories:

- `openclaw-telegram-enhanced`
- `openclaw-host-bridge`
- `openclaw-runtime-distribution`

Instead, it explains how OpenClaw uses the shared platform.

## What This Directory Covers

- OpenClaw runtime contract on the platform
- OpenClaw platform-side architecture and owner model
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

Its platform-specific scripts, runbooks, and operator guidance now live under
this product directory so the shared platform layer stays product-neutral.

OpenClaw is also the reference fully governed product path today:

- stage candidate and rehearsal evidence are explicit Git-managed release
  objects
- prod promotion reuses the approved stage digest instead of rebuilding
- post-promotion prod smoke or UAT is recorded separately from stage approval
- prod runtime now has a bounded governed lifecycle state so OpenClaw can be
  deliberately suspended without tearing down unrelated prod services

For small Telegram-only fixes, OpenClaw can also use a separate immutable
Telegram overlay artifact without rebuilding the full gateway image. That lane
is allowed only on top of a platform-qualified OpenClaw base, must be pinned by
digest, and may promote to prod only by reusing the exact approved stage
candidate on the same qualified base image.

## Start Here

- [AGENTS.md](AGENTS.md)
- [architecture-and-owner-model.md](architecture-and-owner-model.md)
- [runtime-contract.md](runtime-contract.md)
- [dependencies.md](dependencies.md)
- [host-integration.md](host-integration.md)
- [visibility-and-operations.md](visibility-and-operations.md)
- [runbooks/access-openclaw.md](runbooks/access-openclaw.md)
- [runbooks/manage-prod-lifecycle.md](runbooks/manage-prod-lifecycle.md)
- [scripts/README.md](scripts/README.md)
- [skills-src/README.md](skills-src/README.md)
- [runbooks/README.md](runbooks/README.md)

For shared platform context, also see:

- [../../scripts/README.md](../../scripts/README.md)
- [../../docs/README.md](../../docs/README.md)
