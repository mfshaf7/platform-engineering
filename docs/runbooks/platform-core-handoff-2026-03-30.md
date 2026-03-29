# Platform-Core Handoff 2026-03-30

## Current Live State

- `Platform-Core` is the authoritative WSL runtime path.
- Default WSL user in `Platform-Core` is `mfshaf7`.
- `k3s` is active in `Platform-Core`.
- `openclaw-host-bridge.service` is active in `Platform-Core`.
- `openclaw-host-recovery.service` is active in `Platform-Core`.
- `openclaw-host-stack.target` is active in `Platform-Core`.
- Windows scheduled task `PlatformCoreHostStack` exists and is the active
  startup path.
- Legacy Windows scheduled tasks `OpenClawHostStack`, `OpenClaw Node`, and
  `OpenClawPcControlBridge` have been removed as retired startup paths.
- Legacy repo copies at `/opt/openclaw-host-bridge` and
  `/opt/platform-engineering` have been removed after path cutover.
- Windows `127.0.0.1:18789`, `::1:18789`, and `localhost:18789` all resolve to
  the `Platform-Core` `k3s` gateway and return `200` on `/healthz`.
- `openclaw-gateway-stage` is `Synced` and `Healthy` in Argo at revision
  `6ca129c4bcc741b8cccc1697051064b311171412`.
- `openclaw-observability-stage` is `Synced` and `Healthy` in Argo.
- The legacy Docker gateway `upstream-openclaw-openclaw-gateway-1` is stopped.

## Verified Legacy Runtime Dependencies

Live `docker inspect` established that the legacy gateway depended on only two
bind mounts:

- `/home/mfshaf7/.openclaw -> /home/node/.openclaw`
- `/home/mfshaf7/.openclaw/workspace -> /home/node/.openclaw/workspace`

The dependency classification after verification is:

- runtime state dependency: `/home/mfshaf7/.openclaw`
- runtime workspace dependency: `/home/mfshaf7/.openclaw/workspace`
- build-only repo dependency: `openclaw-telegram-enhanced`
- host tooling dependency: `openclaw-host-bridge`
- deployment/build composition repo: `openclaw-isolated-deployment`

## Repo Migration Into Platform-Core

The legacy Ubuntu repo set has been copied into `Platform-Core` under
`/home/mfshaf7/projects`:

- `openclaw-host-bridge`
- `openclaw-isolated-deployment`
- `openclaw-telegram-enhanced`
- `platform-engineering`

The moved `platform-engineering` checkout from legacy Ubuntu was stale relative
to the pushed live cutover state, so it was preserved as:

- `/home/mfshaf7/projects/platform-engineering.legacy-2026-03-30`

The active working copy was then replaced with a clean local clone of the live
authoritative repo:

- `/home/mfshaf7/projects/platform-engineering`

`/home/mfshaf7/.openclaw/workspace` was also copied into `Platform-Core` with
its `.git` metadata intact.

## Immediate Next Step

The direct migration and persistence hardening are complete. The next
engineering step is not more Docker work. It is cleanup and stabilization:

1. keep the legacy Docker gateway stopped while the `k3s` runtime soaks
2. later, replace localhost-style access with a named service endpoint
