# Bootstrap Fresh WSL Distro

## Purpose

This runbook defines the platform-managed path for replacing an unreliable WSL
distribution with a fresh one that can host both the OpenClaw host stack and
the local `k3s` control plane.

## Target Shape

The target distro must end up with:

- `systemd` enabled through `/etc/wsl.conf`
- the canonical `openclaw-host-bridge` checkout present at `/home/mfshaf7/projects/openclaw-host-bridge`
- the platform repo available to run Ansible playbooks
- local policy and OpenClaw config files created outside Git
- `k3s` installed through the platform Ansible role

## Bootstrap Sequence

1. Create and launch the new Ubuntu WSL distro.
2. Clone:
   - `platform-engineering`
   - `openclaw-host-bridge`
3. Place the host-bridge checkout at `/home/mfshaf7/projects/openclaw-host-bridge` or override the
   Ansible variable if a different path is required.
4. Install the host runtime prerequisites needed by the bridge:
   - Node at the path configured by `openclaw_host_bridge_node_bin_dir`
   - local `policy.local.json`
   - local `openclaw.json`
5. Confirm these paths exist before provisioning:
   - `{{ openclaw_host_bridge_root }}/scripts/start-openclaw-host-stack-tmux.sh`
   - `{{ openclaw_host_bridge_config_path }}`
   - `{{ openclaw_openclaw_config_path }}`
   - `{{ openclaw_host_bridge_node_bin_dir }}/node`
6. Run [ansible/playbooks/provision-wsl-host.yml](../../ansible/playbooks/provision-wsl-host.yml).
7. Restart the distro so WSL reloads `/etc/wsl.conf` with `systemd=true`.
8. Run [ansible/playbooks/provision-k3s-node.yml](../../ansible/playbooks/provision-k3s-node.yml).
9. Render the Windows bootstrap artifact with `make render-windows-bootstrap`.
   The committed default distro name is `Platform-Core`.
   If the actual distro name differs, pass an override such as
   `ANSIBLE_EXTRA_VARS="openclaw_windows_wsl_distro=Platform-Core"`.
10. Run the rendered PowerShell script on Windows to register the scheduled task.
11. Run `make verify-platform-host` and require a clean verification result.
12. Continue with [bootstrap-k3s.md](bootstrap-k3s.md) and then the remaining
   platform bootstrap flow.

## Recovery Checkpoint For Interrupted First-Run

If the freshly created `Platform-Core` distro stalls during first-run setup and
subsequent `wsl.exe` access also blocks, stop before any additional migration
or cutover work and recover the distro first.

Required recovery sequence:

1. warn that the next step may disconnect the current session
2. run `wsl.exe --shutdown`
3. run `wsl.exe -l -v`
4. enter `Platform-Core` as `root`
5. create and configure Linux user `mfshaf7`
6. resume this runbook at repository clone, local-config creation, and Ansible
   provisioning

Do not switch the canonical Linux identity away from `mfshaf7`.

Recommended pickup prompt before the shutdown step:

> Pickup point: `Platform-Core` first-run recovery. Next step is
> `wsl.exe --shutdown`, which may disconnect this session. After reconnect,
> re-check `wsl.exe -l -v`, enter `Platform-Core` as `root`, create/configure
> user `mfshaf7`, and continue WSL bootstrap.

## Migration Safety Rules

- do not cut production traffic over to the new distro until `make verify-platform-host` passes
- bring the new platform host up in parallel first, then perform a controlled cutover, then cleanup
- the old runtime, including Docker-backed pieces, may be stopped or removed during controlled cutover if required for a clean migration
- if cutover fails, restore the previously healthy runtime path first and fix the new host after service is back

For the full cutover sequence, use:

- [migrate-to-platform-core.md](migrate-to-platform-core.md)

## Verification

Verify all of:

- `make verify-platform-host` passes
- `systemctl is-system-running` reports a valid `systemd` session
- `systemctl is-active openclaw-host-stack.target` reports `active`
- `systemctl is-active openclaw-host-bridge.service` reports `active`
- `systemctl is-active openclaw-host-recovery.service` reports `active`
- `kubectl get nodes` succeeds
- the host-bridge checkout contains the supervisor scripts
- the configured Node binary and both local config files exist

## Notes

The platform repo does not commit local secret-bearing files for the host stack.
Those still need to be created inside the new distro before the stack is
started.
