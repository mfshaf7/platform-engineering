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
- Windows scheduled task `OpenClawHostStack` remains disabled.
- Windows `127.0.0.1:18789`, `::1:18789`, and `localhost:18789` all resolve to
  the `Platform-Core` `k3s` gateway and return `200` on `/healthz`.
- `openclaw-gateway-stage` is `Synced` and `Healthy` in Argo at revision
  `211869ba1aa11e82c0bd3e5f29b47791d119e1c3`.
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

The direct migration is complete. The next engineering step is not more Docker
work. It is hardening:

1. validate reboot and Windows logon persistence against `Platform-Core`
2. keep the legacy Docker gateway stopped while the `k3s` runtime soaks
3. later, replace localhost-style access with a named service endpoint
