# Migrate to Platform-Core

This runbook covers the migration from the legacy Docker-backed host path into the
managed `Platform-Core` distro.

## Current Recovery Checkpoint

The first-run distro recovery is complete, the host-control path is healthy in
`Platform-Core`, and a replacement OpenClaw gateway is now running in
`Platform-Core` `k3s`.

Observed live state after recovery:

- Windows scheduled task `PlatformCoreHostStack` exists
- Windows scheduled task `OpenClawHostStack` remains disabled
- `Platform-Core` is accessible as Linux user `mfshaf7`
- `openclaw-host-bridge.service` is active in `Platform-Core`
- `openclaw-host-recovery.service` is active in `Platform-Core`
- `openclaw-host-stack.target` is active in `Platform-Core`
- `k3s` is active in `Platform-Core`
- Windows persistence now starts the platform-managed `systemd` host stack
  directly through `PlatformCoreHostStack`
- Windows localhost forwarding for `48721` and `48722` has been repaired to the
  current `Platform-Core` IP
- the legacy runtime container can reach both:
  - `http://host.docker.internal:48721/healthz`
  - `http://host.docker.internal:48722/healthz`
- the stage replacement runtime is now verified in `k3s`:
  - pod-local `http://127.0.0.1:18789/healthz` returns `200`
  - service `http://openclaw-gateway:18789/healthz` returns `200`
  - distro IP `http://172.27.88.8:18789/healthz` returns `200`
  - Windows can reach `http://172.27.88.8:18789/healthz`
  - authenticated bridge and recovery operations succeed from the `k3s` gateway pod
- the legacy Docker runtime container has been stopped after direct cutover validation:
  `upstream-openclaw-openclaw-gateway-1`

Current post-cutover state:

- Windows `127.0.0.1:18789` is forwarded to `172.27.88.8:18789` in `Platform-Core` and returns `200`
- Windows `::1:18789` is forwarded to `172.27.88.8:18789` in `Platform-Core` and returns `200`
- Windows `localhost:18789` resolves to the `Platform-Core` `k3s` gateway without Docker in the request path
- `openclaw-gateway-stage` in Argo is `Synced` and `Healthy` at revision
  `6ca129c4bcc741b8cccc1697051064b311171412`
- `openclaw-observability-stage` in Argo is `Synced` and `Healthy`
- `upstream-openclaw-openclaw-gateway-1` is stopped after localhost cutover
  was revalidated against the `k3s` gateway

Legacy repo migration into `Platform-Core` is also complete:

- `/home/mfshaf7/projects/openclaw-host-bridge` is present
- `/home/mfshaf7/projects/openclaw-isolated-deployment` is present
- `/home/mfshaf7/projects/openclaw-telegram-enhanced` is present
- `/home/mfshaf7/projects/platform-engineering` is present as a clean clone of
  the pushed authoritative repo state
- `/home/mfshaf7/.openclaw/workspace` is present and still contains its `.git`
  metadata

The next intended migration step is:

1. remove or archive any legacy Docker artifacts that are no longer needed after
   stable soak time
2. remove or disable legacy Windows startup artifacts once rollback risk is acceptable
3. move the gateway from localhost-style compatibility access to a named service
   endpoint in a later phase

## Phase 3: Controlled Cutover

1. Register and validate the Windows scheduled task for `Platform-Core`.
2. Stop the old runtime entrypoints that would conflict with the new host path.
   This may include Docker containers, old WSL tasks, or legacy startup helpers.
3. Bring the new platform-managed startup path into service.
4. Verify that the OpenClaw runtime can reach the new host bridge and recovery
   endpoints.
5. Re-run `make verify-platform-host`.

This is the first phase where it is acceptable to stop or kill the old runtime.
Do it deliberately and record what was stopped.

## Phase 4: Post-Cutover Verification

Verify all of:

- `make verify-platform-host` passes
- Windows bootstrap now points at `Platform-Core`
- the OpenClaw runtime is healthy
- the OpenClaw runtime can reach the new host bridge
- the OpenClaw runtime can reach the recovery endpoint
- runtime behavior is at least as healthy as before cutover

If any of these checks fail, move to rollback immediately.

## Phase 5: Cleanup

After the new path is healthy:

1. remove or disable old scheduled tasks
2. stop and remove obsolete Docker-backed runtime pieces if they are no longer part of the target stack
3. remove outdated WSL startup helpers that are no longer in the supported platform path
4. record the cleanup result

Cleanup happens only after post-cutover verification succeeds.

## Rollback Trigger

Rollback immediately if:

- the runtime cannot reach the new host bridge
- the runtime cannot reach the recovery endpoint
- `k3s` is unhealthy on `Platform-Core`
- Windows bootstrap does not reliably start the new stack
- the new platform path regresses service health

## Rollback Path

1. stop the new cutover path if it is causing conflicts
