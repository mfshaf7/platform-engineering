# Access OpenClaw

## Purpose

This runbook defines how operators access OpenClaw directly on this platform.

## Current Access Reality

- prod OpenClaw is active by default in namespace `openclaw`, but may be
  deliberately suspended through the governed prod lifecycle contract
- stage OpenClaw is suspended by default and only exists during deliberate test
  windows
- OpenClaw does not currently expose a shared browser UI
- Telegram is the primary user-facing surface

## User-Facing Access

Normal user interaction happens through Telegram, not through a browser.

If you are testing a promoted runtime behavior, the meaningful checks are:

- normal Telegram reply
- file send
- screenshot send
- host-control routing
- admin or high-risk host-control behavior only when explicitly enabled

## Operator Access To Prod

Inspect the live prod runtime with:

```bash
k3s kubectl -n openclaw get deploy,svc,pod
k3s kubectl -n openclaw port-forward svc/openclaw-gateway 18789:18789
curl http://127.0.0.1:18789/healthz
curl http://127.0.0.1:18789/readyz
```

Useful operator checks:

```bash
k3s kubectl -n openclaw logs deploy/openclaw-gateway --tail=200
k3s kubectl -n argocd get application openclaw-gateway
python3 products/openclaw/scripts/set_prod_environment_state.py status
```

Treat the port-forwarded endpoint as an operator/debug surface, not an end-user
application.

Read-only Telegram operator inventory:

- use `/platform` inside the intended Telegram operator topic
- use `/platform endpoints`, `/platform health`, `/platform govern`, or
  `/platform <component>`
- this surface is catalog-driven from
  `products/openclaw/platform-operator-catalog.yaml`

## Operator Access To Stage

Resume stage only when you need a rehearsal or validation window:

- local stage runtime config must exist at
  `~/.openclaw-stage/openclaw.stage.k3s.json`
- that config must explicitly set `channels.telegram.commands.native: true`
  or Telegram-native operator commands such as `/platform` will fall back to
  the embedded agent path instead of the deterministic handler
- stage resume now validates one authenticated read-only bridge request after
  `/healthz`, not just service liveness; if the local audit path under
  `~/.openclaw-stage/logs/openclaw-host-audit/` is not writable, resume should
  fail instead of leaving a bridge that crashes on the first real request

```bash
python3 products/openclaw/scripts/set_stage_environment_state.py resume --components gateway,version
```

Then inspect the stage gateway:

```bash
k3s kubectl -n openclaw-stage get deploy,svc,pod
k3s kubectl -n openclaw-stage port-forward svc/openclaw-gateway 28789:18789
curl http://127.0.0.1:28789/healthz
curl http://127.0.0.1:28789/readyz
```

When the rehearsal is complete, suspend stage again:

```bash
python3 products/openclaw/scripts/set_stage_environment_state.py suspend
```

## Governing Prod Runtime State

Use the bounded prod lifecycle control when prod OpenClaw must be deliberately
stopped or returned to service:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py status
python3 products/openclaw/scripts/set_prod_environment_state.py suspended --changed-by <operator> --reason <reason>
python3 products/openclaw/scripts/set_prod_environment_state.py live --changed-by <operator> --reason <reason>
```

That control only governs the OpenClaw prod runtime slice. It must not prune
OpenProject or unrelated shared prod services.

## Shared Platform Surfaces Used For OpenClaw

OpenClaw operators will also use shared platform surfaces:

- Argo CD for deployment and sync state
- Vault for operator and secret workflows
- Grafana, Prometheus, and Alertmanager for shared observability

Those entrypoints are documented in:

- [../../../docs/runbooks/access-platform-uis.md](../../../docs/runbooks/access-platform-uis.md)

## Host-Control Evidence

OpenClaw host-control evidence lives outside the cluster boundary in
`openclaw-host-bridge`.

For host-side policy, audit, and bridge runtime details, use the owning repo's
docs and status tooling instead of treating the cluster service as the full
truth.
