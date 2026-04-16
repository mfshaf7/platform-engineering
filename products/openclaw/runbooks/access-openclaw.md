# Access OpenClaw

## Purpose

This runbook defines how operators access OpenClaw directly on this platform.

## Current Access Reality

- prod OpenClaw is active in namespace `openclaw`
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
```

Treat the port-forwarded endpoint as an operator/debug surface, not an end-user
application.

## Operator Access To Stage

Resume stage only when you need a rehearsal or validation window:

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
