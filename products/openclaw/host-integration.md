# Host Integration

OpenClaw host-control actions cross into the host through bridge and recovery
services managed outside Kubernetes.

Current concrete host shape:

- WSL-hosted `openclaw-host-bridge`
- WSL-hosted `openclaw-host-recovery`
- Windows scheduled-task bootstrap
- bridge and recovery supervisor scripts used as the service entrypoints
