# Platform-Core Handoff 2026-03-30

## Status

This document is a historical cutover record from March 30, 2026.

It is not the current source of truth for ongoing platform operations. Use the
active runbooks and standards under `docs/runbooks/` and `docs/standards/`
instead.

## Current Live State

- `Platform-Core` is the authoritative WSL runtime path.
- Default WSL user in `Platform-Core` is `mfshaf7`.
- `Platform-Core` is the default WSL distribution.
- The legacy `Ubuntu` WSL distro has been removed.
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
- Argo roots are now `platform-root-shared`, `platform-root-stage`, and
  `platform-root-prod`.
- Shared platform services now reconcile under the `platform-core` AppProject.
- Vault runs as a three-node HA Raft cluster in the `vault` namespace.
- `platform-secrets-stage` and `platform-secrets-prod` are `Synced` and
  `Healthy` through External Secrets Operator backed by Vault.
- `openclaw-gateway-stage`, `openclaw-gateway`, `platform-version-stage`,
  `platform-version`, `openclaw-observability-stage`, and
  `openclaw-observability` are `Synced` and `Healthy` in Argo at revision
  `923daea0601b7097d046a0da6dd4cdf208016fed` for the platform repo-backed
  applications.
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
to the pushed live cutover state. The active working copy was replaced with a
clean local clone of the live authoritative repo:

- `/home/mfshaf7/projects/platform-engineering`

`/home/mfshaf7/.openclaw/workspace` was also copied into `Platform-Core` with
its `.git` metadata intact.

## Immediate Next Step

The direct migration, persistence hardening, governed image delivery,
platform-neutral control-plane rename, and Vault-backed secret centralization
are now in place. The next engineering work is broader platform productization:

1. continue the naming audit so remaining shared components stay product-neutral
2. replace any remaining manual secret bootstrap habits with fully governed
   Vault operator workflows
3. later, replace localhost-style access with a named service endpoint
