# Visibility And Operations

## Runtime Identity

- product namespace: `openclaw` for prod, `openclaw-stage` for stage
- product runtime: gateway deployment reconciled by Argo
- current active build/composition owner: `openclaw-runtime-distribution`

## Health And Readiness

Operators should check:

- Argo application sync and health
- gateway deployment image digest
- in-pod `/healthz`
- in-pod `/readyz` when readiness matters

Health alone is not enough for OpenClaw.

## Product-Specific Functional Checks

Minimum meaningful checks for promoted changes:

- Telegram provider starts
- normal Telegram reply works
- file send works end to end
- screenshot send works end to end
- deterministic host-control routing still works
- admin/high-risk host-control path is either explicitly disabled or explicitly
  verified

## Host Integration Evidence

OpenClaw is the product in this repo that crosses a real host-control boundary.

Relevant evidence surfaces:

- `openclaw-host-bridge` `/healthz`
- `scripts/status-openclaw-host-stack.sh`
- bridge audit logs
- recovery service health
- stage on-demand bridge lifecycle for stage rehearsals

## Release Evidence

For governed release and promotion, operators should be able to identify:

- approved source SHAs
- approved image digest
- platform revision that recorded the digest
- Argo revision that deployed it
- one real functional verification result
