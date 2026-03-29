# Host Stack Rollout

## Purpose

This runbook maps the platform-engineering host model to the current OpenClaw
host stack.

## Expected Inputs

- canonical `openclaw-host-bridge` checkout present on the WSL host
- local policy file created at the configured host-bridge policy path
- OpenClaw config present at the configured OpenClaw config path
- Node runtime available at the configured Node bin directory

## Managed Assets

The platform repo manages:

- `openclaw-host-bridge.service`
- `openclaw-host-recovery.service`
- `openclaw-host-stack.target`
- `/etc/openclaw/host-bridge/openclaw-host-bridge.env`

## Windows Bootstrap

The current Windows-side bootstrap remains a scheduled task launching:

- `scripts/start-openclaw-host-stack-tmux.sh`

This matches the current validated runtime shape while the platform model
introduces cleaner systemd ownership inside WSL.
