# Host Integration

OpenClaw host-control actions cross into the host through bridge and recovery
services managed outside Kubernetes.

For the broader product boundary and owner split, see
[architecture-and-owner-model.md](architecture-and-owner-model.md).

Current concrete host shape:

- WSL-hosted `openclaw-host-bridge`
- WSL-hosted `openclaw-host-recovery`
- Windows scheduled-task bootstrap
- bridge and recovery supervisor scripts used as the service entrypoints
