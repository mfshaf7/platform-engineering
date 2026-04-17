# Manage Prod Lifecycle

## Purpose

This runbook defines the governed lifecycle control for the OpenClaw prod
runtime.

The bounded initial states are:

- `live`
- `suspended`

This control affects only the OpenClaw prod runtime slice:

- `openclaw-gateway-app.yaml`
- `platform-secrets-app.yaml`
- `platform-version-app.yaml`

It must not prune unrelated prod applications such as OpenProject or shared
observability.

## Local Operator Path

Inspect the current state:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py status
```

Suspend prod OpenClaw:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py suspended \
  --changed-by "<operator>" \
  --reason "<reason>" \
  --incident-ref "<ticket-or-incident>" \
  --note "<optional note>"
```

Return prod OpenClaw to `live`:

```bash
python3 products/openclaw/scripts/set_prod_environment_state.py live \
  --changed-by "<operator>" \
  --reason "<reason>" \
  --incident-ref "<ticket-or-incident>" \
  --note "<optional note>"
```

Equivalent Make target:

```bash
make openclaw-prod-state STATE=suspended CHANGED_BY=<operator> REASON=<reason>
```

## GitHub Workflow Path

Use `.github/workflows/manage-prod-environment.yaml` when you want the
repository to create the lifecycle branch under the `prod` environment gate.

## Operational Effects

When prod state is `suspended`:

- the OpenClaw prod Argo applications are removed from the prod root
- a lifecycle configmap remains in `argocd` as explicit state evidence
- `environments/prod/verification.yaml` is reset to `inactive`
- future prod smoke/UAT remains inactive until prod is returned to `live`

When prod state returns to `live`:

- the OpenClaw prod Argo applications are restored to the prod root
- `environments/prod/verification.yaml` is reset to `pending`
- fresh prod smoke/UAT is required before treating prod as operationally
  complete

## Promotion Interaction

Promotion may still update the prod contract while prod is suspended.

That does not bring prod back online by itself. The lifecycle state still owns
whether the prod OpenClaw runtime is active.

This allows operators to prepare a fixed prod contract while keeping prod
quiet, then return prod to `live` only when ready.
