# Visibility And Operations

## Runtime Identity

- product namespace: `openclaw` for prod, `openclaw-stage` for stage
- product runtime: gateway deployment reconciled by Argo
- current active build/composition owner: `openclaw-runtime-distribution`
- primary user-facing surface: Telegram
- current browser UI posture: none for OpenClaw itself

## Health And Readiness

Operators should check:

- Argo application sync and health
- gateway deployment image digest
- in-pod `/healthz`
- in-pod `/readyz` when readiness matters

Health alone is not enough for OpenClaw.

## Direct Access Model

- prod is `live` by default in namespace `openclaw`, but may be deliberately
  shifted into:
  - `traffic-stopped`
  - `suspended`
  - `quarantined`
  through the governed prod lifecycle contract
- stage is suspended by default and does not have a live gateway unless
  deliberately resumed
- the product does not currently expose a browser application or dashboard of
  its own
- direct operator inspection should use the product access runbook:
  [runbooks/access-openclaw.md](runbooks/access-openclaw.md)
- shared dashboards and control-plane UIs are documented in:
  [../../docs/runbooks/access-platform-uis.md](../../docs/runbooks/access-platform-uis.md)

## Product-Specific Functional Checks

Minimum stage rehearsal checks for promoted changes:

- Telegram provider starts
- normal Telegram reply works
- file send works end to end
- screenshot send works end to end
- deterministic host-control routing still works
- admin/high-risk host-control path is either explicitly disabled or explicitly
  verified

Minimum post-promotion prod smoke or UAT checks:

- reconciliation state matches the promoted digest
- one real inbound prod Telegram interaction succeeds
- one read-only prod operator interaction succeeds, for example `/platform`

If prod OpenClaw is deliberately suspended, prod smoke/UAT remains inactive
until the lifecycle returns to `live`. The same rule applies when prod is
`traffic-stopped` or `quarantined`.

For OpenClaw specifically, `traffic-stopped` is a deployment-level quiet mode:
the prod gateway application is removed while selected support surfaces remain.
It is not implemented as Telegram-specific send or polling suppression inside
the channel plugin.

## Host Integration Evidence

OpenClaw is the product in this repo that crosses a real host-control boundary.

Relevant evidence surfaces:

- `openclaw-host-bridge` `/healthz`
- `scripts/status-openclaw-host-stack.sh`
- bridge audit logs
- recovery service health
- stage on-demand bridge lifecycle for stage rehearsals
- `products/openclaw/platform-operator-catalog.yaml`
- `environments/stage/release-candidate.yaml`
- `environments/stage/verification.yaml`
- `environments/stage/promotion-readiness.yaml`
  - retained OpenClaw product-local filename for the standardized stage
    readiness decision
- `environments/prod/openclaw-lifecycle.yaml`
- `environments/prod/verification.yaml`

## Release Evidence

For governed release and promotion, operators should be able to identify:

- approved source SHAs
- approved image digest
- platform revision that recorded the digest
- Argo revision that deployed it
- recorded prod smoke or UAT evidence for the promoted contract when prod was
  affected
