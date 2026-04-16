# Host Stack Rollout

## Purpose

This runbook maps the platform-engineering host model to the current OpenClaw
host stack.

## Expected Inputs

- canonical `openclaw-host-bridge` checkout present on the WSL host
- local prod policy and OpenClaw config present at the configured paths
- local stage policy and OpenClaw config present at the configured stage paths
- when stage Telegram-native operator commands are part of the rehearsal
  surface, the stage OpenClaw config must explicitly set
  `channels.telegram.commands.native: true`
- Node runtime available at the configured Node bin directory
- WSL distro restarted after enabling `systemd` in `/etc/wsl.conf`

## Managed Assets

The platform repo manages:

- `openclaw-host-bridge.service`
- `openclaw-host-recovery.service`
- `openclaw-host-stack.target`
- `/etc/openclaw/host-bridge/openclaw-host-bridge.env`
- `ansible/generated/openclaw-host-stack-windows-bootstrap.ps1`

## Windows Bootstrap

The Windows-side bootstrap is a scheduled task that starts the platform-managed
bootstrap sequence inside WSL:

- `systemctl start openclaw-host-stack.target`

When transit orchestration is enabled, that same bootstrap path may also:

- start the separate transit distro
- wait for transit Vault health
- start `Platform-Core`
- in `cold` mode, stop the transit Vault service again after workload Vault is
  unsealed

The platform repo now renders the matching Windows bootstrap artifact with:

- `make render-windows-bootstrap`
- `make render-windows-bootstrap ANSIBLE_EXTRA_VARS="platform_windows_wsl_distro=Platform-Core"`

The rendered script path is:

- `ansible/generated/openclaw-host-stack-windows-bootstrap.ps1`

The task should run the Windows-local mirrored copy at:

- `%LOCALAPPDATA%\OpenClaw\bootstrap\openclaw-host-stack-windows-bootstrap.ps1`

`make render-windows-bootstrap` refreshes both the repo-local generated artifact
and the Windows-local copy used by the scheduled task.

The platform-managed task name is:

- `PlatformCoreHostStack`

After post-cutover verification and one real reboot/logon validation, retire
the legacy Windows startup hooks and keep `PlatformCoreHostStack` as the only
supported Windows bootstrap path.

This keeps Windows responsible only for logon-triggered WSL entry while systemd
inside WSL owns bridge and recovery supervision.

Transit bootstrap orchestration remains optional and is disabled by default
until the separate transit trust root is actually deployed.

For full replacement of an unreliable distro, use:

- [bootstrap-wsl-distro.md](bootstrap-wsl-distro.md)
