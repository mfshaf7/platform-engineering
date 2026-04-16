# Dependencies

OpenClaw currently depends on:

- gateway runtime image assembled by `openclaw-runtime-distribution`
- Telegram runtime integration from `openclaw-telegram-enhanced`
- host bridge from `openclaw-host-bridge`
- host recovery on the WSL host
- Vault and External Secrets for runtime secret delivery
- Argo CD and environment contracts for governed rollout

## Dependency Classes

### Product composition

- OpenClaw base runtime
- packaged Telegram runtime
- active `host-control-openclaw-plugin`

### Host-side dependencies

- `openclaw-host-bridge`
- `openclaw-host-recovery`
- Windows Task Scheduler bootstrap
- WSL `systemd`

### Platform dependencies

- `platform-engineering` environment contracts
- Argo CD reconciliation
- Vault-backed secret delivery

## Related Docs

- [architecture-and-owner-model.md](architecture-and-owner-model.md)
- [runtime-contract.md](runtime-contract.md)
- [host-integration.md](host-integration.md)
