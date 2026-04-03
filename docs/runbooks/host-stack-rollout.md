# Host Stack Rollout

## Purpose

This runbook maps the platform-engineering host model to the current OpenClaw
host stack.

## Expected Inputs

- canonical `openclaw-host-bridge` checkout present on the WSL host
- local policy file created at the configured host-bridge policy path
- OpenClaw config present at the configured OpenClaw config path
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
- `make render-windows-bootstrap ANSIBLE_EXTRA_VARS="openclaw_windows_wsl_distro=Platform-Core"`

The rendered script path is:

- `ansible/generated/openclaw-host-stack-windows-bootstrap.ps1`

Run that PowerShell script on Windows to register the scheduled task for the
configured distro and host-bridge root.

The platform-managed task name is:

- `PlatformCoreHostStack`

During migration, keep the legacy Windows task `OpenClawHostStack` available as
the rollback path until post-cutover verification succeeds.

This keeps Windows responsible only for logon-triggered WSL entry while systemd
inside WSL owns bridge and recovery supervision.

Transit bootstrap orchestration remains optional and is disabled by default
until the separate transit trust root is actually deployed.

For full replacement of an unreliable distro, use:

- [bootstrap-wsl-distro.md](bootstrap-wsl-distro.md)
